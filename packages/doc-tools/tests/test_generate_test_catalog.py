import argparse
import json
from pathlib import Path

import pytest

from doc_tools.generate_test_catalog import (
    BehaviorCase,
    GroupNode,
    build_group_tree,
    build_sections,
    count_cases,
    parse_csharp_catalog_json,
    parse_go_test_json,
    parse_pytest_junit,
    parse_section_arg,
    parse_vitest_json,
    render_html,
    render_markdown,
    route_cases_to_specs,
    SectionSpec,
)


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


class TestGoのテスト結果のパース:
    def test_親テストは除かれ末端のケースだけが残る(self, tmp_path: Path):
        pkg = "example.com/svc/internal/handler"
        lines = [
            {"Action": "pass", "Package": pkg, "Test": "TestX/対象A/ケース1"},
            {"Action": "pass", "Package": pkg, "Test": "TestX/対象A/ケース2"},
            {"Action": "pass", "Package": pkg, "Test": "TestX/対象A"},
            {"Action": "pass", "Package": pkg, "Test": "TestX"},
        ]
        path = _write(tmp_path / "go.json", "\n".join(json.dumps(x) for x in lines))
        assert parse_go_test_json(path) == [
            BehaviorCase(("対象A",), "ケース1", False, pkg),
            BehaviorCase(("対象A",), "ケース2", False, pkg),
        ]

    def test_先頭のテスト関数名は対象要素から除かれる(self, tmp_path: Path):
        pkg = "example.com/svc/internal/repository"
        line = {"Action": "pass", "Package": pkg, "Test": "TestSaveOrder/注文の保存/正しく保存される"}
        path = _write(tmp_path / "go.json", json.dumps(line))
        assert parse_go_test_json(path) == [
            BehaviorCase(("注文の保存",), "正しく保存される", False, pkg),
        ]

    def test_サブテストの無いテスト関数はケース名がテスト関数名になる(self, tmp_path: Path):
        pkg = "example.com/svc/internal/handler"
        line = {"Action": "pass", "Package": pkg, "Test": "TestBare"}
        path = _write(tmp_path / "go.json", json.dumps(line))
        assert parse_go_test_json(path) == [
            BehaviorCase((), "TestBare", False, pkg),
        ]

    def test_skipアクションのケースは未検証扱いになる(self, tmp_path: Path):
        pkg = "example.com/svc/internal/handler"
        line = {"Action": "skip", "Package": pkg, "Test": "TestX/対象A/未実装のケース"}
        path = _write(tmp_path / "go.json", json.dumps(line))
        assert parse_go_test_json(path)[0].is_skipped is True

    def test_パッケージパスが由来になる(self, tmp_path: Path):
        pkg = "example.com/svc/internal/repository"
        line = {"Action": "pass", "Package": pkg, "Test": "TestX/対象/ケース"}
        path = _write(tmp_path / "go.json", json.dumps(line))
        assert parse_go_test_json(path)[0].source_file == pkg

    def test_空行は無視される(self, tmp_path: Path):
        pkg = "example.com/svc/internal/handler"
        line = {"Action": "pass", "Package": pkg, "Test": "TestX/対象/ケース"}
        path = _write(tmp_path / "go.json", json.dumps(line) + "\n\n")
        assert len(parse_go_test_json(path)) == 1

    def test_JSONとして読めない行があるときValueErrorになる(self, tmp_path: Path):
        path = _write(tmp_path / "go.json", "これはJSONではない")
        with pytest.raises(ValueError):
            parse_go_test_json(path)


class TestpytestのJUnitXMLのパース:
    def _junit(self, testcases: str) -> str:
        return f'<testsuites><testsuite>{testcases}</testsuite></testsuites>'

    def test_Test始まりクラス以降がグループ連鎖になる(self, tmp_path: Path):
        xml = self._junit(
            '<testcase classname="tests.test_shop.Test送料計算" name="test_無料になる"/>'
        )
        path = _write(tmp_path / "junit.xml", xml)
        assert parse_pytest_junit(path) == [
            BehaviorCase(("送料計算",), "無料になる", False, "tests.test_shop"),
        ]

    def test_ネストクラスは多段のグループ連鎖になる(self, tmp_path: Path):
        xml = self._junit(
            '<testcase classname="tests.test_shop.Test送料計算.Test国際便" name="test_割増になる"/>'
        )
        path = _write(tmp_path / "junit.xml", xml)
        assert parse_pytest_junit(path) == [
            BehaviorCase(("送料計算", "国際便"), "割増になる", False, "tests.test_shop"),
        ]

    def test_クラスの無い関数テストはグループ連鎖が空になる(self, tmp_path: Path):
        xml = self._junit('<testcase classname="tests.test_shop" name="test_起動する"/>')
        path = _write(tmp_path / "junit.xml", xml)
        assert parse_pytest_junit(path) == [
            BehaviorCase((), "起動する", False, "tests.test_shop"),
        ]

    def test_skipped要素を持つケースは未検証扱いになる(self, tmp_path: Path):
        xml = self._junit(
            '<testcase classname="tests.test_shop.Test送料計算" name="test_未実装"><skipped/></testcase>'
        )
        path = _write(tmp_path / "junit.xml", xml)
        assert parse_pytest_junit(path)[0].is_skipped is True

    def test_name属性の無いケースがあるときValueErrorになる(self, tmp_path: Path):
        xml = self._junit('<testcase classname="tests.test_shop.Test送料計算"/>')
        path = _write(tmp_path / "junit.xml", xml)
        with pytest.raises(ValueError):
            parse_pytest_junit(path)

    def test_classname属性の無いケースがあるときValueErrorになる(self, tmp_path: Path):
        xml = self._junit('<testcase name="test_無料になる"/>')
        path = _write(tmp_path / "junit.xml", xml)
        with pytest.raises(ValueError):
            parse_pytest_junit(path)


class TestvitestのJSONのパース:
    def _report(self, file_name: str, assertions: list[dict]) -> dict:
        return {"testResults": [{"name": file_name, "assertionResults": assertions}]}

    def test_describeのネストがグループ連鎖になる(self, tmp_path: Path):
        report = self._report(
            "src/stores/deckStore.test.ts",
            [{"ancestorTitles": ["デッキストア", "初期化"], "title": "空で始まる", "status": "passed"}],
        )
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        assert parse_vitest_json(path) == [
            BehaviorCase(("デッキストア", "初期化"), "空で始まる", False, "src/stores/deckStore.test.ts"),
        ]

    def test_ファイルのパスが由来になる(self, tmp_path: Path):
        report = self._report(
            "src/stores/deckStore.test.ts",
            [{"ancestorTitles": [], "title": "起動する", "status": "passed"}],
        )
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        assert parse_vitest_json(path)[0].source_file == "src/stores/deckStore.test.ts"

    def test_絶対パスの由来は実行位置からの相対パスになる(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        report = self._report(
            str(tmp_path / "src/stores/deckStore.test.ts"),
            [{"ancestorTitles": [], "title": "起動する", "status": "passed"}],
        )
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        assert parse_vitest_json(path)[0].source_file == "src/stores/deckStore.test.ts"

    def test_実行位置の外を指す絶対パスの由来があるときValueErrorになる(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        report = self._report(
            "/elsewhere/src/stores/deckStore.test.ts",
            [{"ancestorTitles": [], "title": "起動する", "status": "passed"}],
        )
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        with pytest.raises(ValueError, match="実行位置の配下に無いパスです"):
            parse_vitest_json(path)

    def test_skippedステータスは未検証扱いになる(self, tmp_path: Path):
        report = self._report(
            "src/stores/deckStore.test.ts",
            [{"ancestorTitles": [], "title": "未実装", "status": "skipped"}],
        )
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        assert parse_vitest_json(path)[0].is_skipped is True

    def test_passedステータスは検証済み扱いになる(self, tmp_path: Path):
        report = self._report(
            "src/stores/deckStore.test.ts",
            [{"ancestorTitles": [], "title": "起動する", "status": "passed"}],
        )
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        assert parse_vitest_json(path)[0].is_skipped is False

    def test_titleの無いケースがあるときValueErrorになる(self, tmp_path: Path):
        report = self._report("src/x.test.ts", [{"ancestorTitles": [], "status": "passed"}])
        path = _write(tmp_path / "vitest.json", json.dumps(report))
        with pytest.raises(ValueError):
            parse_vitest_json(path)


class TestCシャープの中間JSONのパース:
    def test_対象がグループ_caseがケース名になる(self, tmp_path: Path):
        records = [
            {"target": "送料計算", "case": "3000 円のとき無料になる", "skipped": False, "source": "Battle.Tests.Fee"}
        ]
        path = _write(tmp_path / "csharp.json", json.dumps(records))
        assert parse_csharp_catalog_json(path) == [
            BehaviorCase(("送料計算",), "3000 円のとき無料になる", False, "Battle.Tests.Fee"),
        ]

    def test_Theoryを展開した複数行が個別のケースになる(self, tmp_path: Path):
        records = [
            {"target": "送料計算", "case": "閾値未満のとき 500 円になる (amount: 2999)", "skipped": False, "source": "Battle.Tests.Fee"},
            {"target": "送料計算", "case": "閾値未満のとき 500 円になる (amount: 0)", "skipped": False, "source": "Battle.Tests.Fee"},
        ]
        path = _write(tmp_path / "csharp.json", json.dumps(records))
        assert parse_csharp_catalog_json(path) == [
            BehaviorCase(("送料計算",), "閾値未満のとき 500 円になる (amount: 2999)", False, "Battle.Tests.Fee"),
            BehaviorCase(("送料計算",), "閾値未満のとき 500 円になる (amount: 0)", False, "Battle.Tests.Fee"),
        ]

    def test_対象が空文字のときグループ連鎖が空になる(self, tmp_path: Path):
        records = [{"target": "", "case": "起動する", "skipped": False, "source": "Battle.Tests.Boot"}]
        path = _write(tmp_path / "csharp.json", json.dumps(records))
        assert parse_csharp_catalog_json(path)[0].group_chain == ()

    def test_skippedが真のケースは未検証扱いになる(self, tmp_path: Path):
        records = [{"target": "送料計算", "case": "未実装", "skipped": True, "source": "Battle.Tests.Fee"}]
        path = _write(tmp_path / "csharp.json", json.dumps(records))
        assert parse_csharp_catalog_json(path)[0].is_skipped is True

    def test_skippedが偽のケースは検証済み扱いになる(self, tmp_path: Path):
        records = [{"target": "送料計算", "case": "3000 円のとき無料になる", "skipped": False, "source": "Battle.Tests.Fee"}]
        path = _write(tmp_path / "csharp.json", json.dumps(records))
        assert parse_csharp_catalog_json(path)[0].is_skipped is False

    @pytest.mark.parametrize(
        "missing_key",
        [
            pytest.param("target", id="target が無いとき target が欠けたことを示すエラーになる"),
            pytest.param("case", id="case が無いとき case が欠けたことを示すエラーになる"),
            pytest.param("skipped", id="skipped が無いとき skipped が欠けたことを示すエラーになる"),
            pytest.param("source", id="source が無いとき source が欠けたことを示すエラーになる"),
        ],
    )
    def test_必須キーの欠けたレコードを読む(self, tmp_path: Path, missing_key):
        record = {
            "target": "送料計算",
            "case": "3000 円のとき無料になる",
            "skipped": False,
            "source": "Battle.Tests.Fee",
        }
        del record[missing_key]
        path = _write(tmp_path / "csharp.json", json.dumps([record]))
        with pytest.raises(ValueError, match=f"レコードに {missing_key} がありません"):
            parse_csharp_catalog_json(path)


class Testグループ木の組み立て:
    def test_同名グループのケースは1つのノードに統合される(self):
        cases = [
            BehaviorCase(("グループA",), "ケース1", False, "s"),
            BehaviorCase(("グループA",), "ケース2", False, "s"),
        ]
        tree = build_group_tree(cases)
        assert list(tree.subgroups["その他"].subgroups) == ["グループA"]
        assert [
            c.case_name for c in tree.subgroups["その他"].subgroups["グループA"].cases
        ] == ["ケース1", "ケース2"]

    def test_グループ連鎖が2段のとき入れ子のノードになる(self):
        tree = build_group_tree([BehaviorCase(("外", "内"), "ケースX", False, "s")])
        assert [
            c.case_name for c in tree.subgroups["その他"].subgroups["外"].subgroups["内"].cases
        ] == ["ケースX"]

    def test_先頭にタグを持つトップレベルグループはタグを見出しとしてその下に置かれる(self):
        tree = build_group_tree([BehaviorCase(("[認証系]ログイン処理",), "ケースX", False, "s")])
        assert list(tree.subgroups) == ["認証系"]
        assert [
            c.case_name for c in tree.subgroups["認証系"].subgroups["ログイン処理"].cases
        ] == ["ケースX"]

    def test_同じタグを持つトップレベルグループが別々の由来にあるとき1つの見出しに集約される(self):
        cases = [
            BehaviorCase(("[認証系]ログイン処理",), "ケース1", False, "pkg/login"),
            BehaviorCase(("[認証系]トークン検証",), "ケース2", False, "pkg/token"),
        ]
        tree = build_group_tree(cases)
        assert list(tree.subgroups) == ["認証系"]
        assert list(tree.subgroups["認証系"].subgroups) == ["ログイン処理", "トークン検証"]

    def test_タグを持たないトップレベルグループはその他の下に置かれる(self):
        tree = build_group_tree([BehaviorCase(("ログイン処理",), "ケースX", False, "s")])
        assert list(tree.subgroups) == ["その他"]
        assert [
            c.case_name for c in tree.subgroups["その他"].subgroups["ログイン処理"].cases
        ] == ["ケースX"]

    def test_2段目以降のグループ名が角括弧で始まっていてもタグとして扱わない(self):
        cases = [BehaviorCase(("[認証系]ログイン処理", "[内側]入力検証"), "ケースX", False, "s")]
        tree = build_group_tree(cases)
        assert list(tree.subgroups["認証系"].subgroups["ログイン処理"].subgroups) == [
            "[内側]入力検証"
        ]

    def test_角括弧の中身が空のときタグとして扱わずグループ名の一部として残る(self):
        tree = build_group_tree([BehaviorCase(("[]ログイン処理",), "ケースX", False, "s")])
        assert list(tree.subgroups) == ["その他"]
        assert list(tree.subgroups["その他"].subgroups) == ["[]ログイン処理"]

    def test_グループ連鎖が空のケースはタグを持つグループとは別にルート直下に置かれる(self):
        cases = [
            BehaviorCase((), "ケースX", False, "s"),
            BehaviorCase(("[認証系]ログイン処理",), "ケースY", False, "s"),
        ]
        tree = build_group_tree(cases)
        assert [c.case_name for c in tree.cases] == ["ケースX"]
        assert list(tree.subgroups) == ["認証系"]


class Testケース数の数え上げ:
    def test_ケースが無い木では0になる(self):
        assert count_cases(GroupNode()) == 0

    def test_ルート直下1件のとき1になる(self):
        tree = build_group_tree([BehaviorCase((), "ケースX", False, "s")])
        assert count_cases(tree) == 1

    def test_入れ子のグループを含めた総数になる(self):
        cases = [
            BehaviorCase((), "ルートのケース", False, "s"),
            BehaviorCase(("外",), "ケース1", False, "s"),
            BehaviorCase(("外", "内"), "ケース2", False, "s"),
        ]
        assert count_cases(build_group_tree(cases)) == 3


class Test由来によるセクション振り分け:
    def test_プレフィクス指定の無いセクションが1件のとき全ケースがそのセクションに入る(self):
        spec = SectionSpec("外", "svc", "go-json", Path("r.json"), None)
        cases = [BehaviorCase((), "ケース", False, "s")]
        assert route_cases_to_specs([spec], cases) == {spec: cases}

    def test_由来がプレフィクスに前方一致するとき対応するセクションに振り分けられる(self):
        outer = SectionSpec("外", "svc", "go-json", Path("r.json"), ("pkg/handler",))
        inner = SectionSpec("内", "svc", "go-json", Path("r.json"), ("pkg/repository",))
        handler_case = BehaviorCase((), "外のケース", False, "pkg/handler/order")
        repo_case = BehaviorCase((), "内のケース", False, "pkg/repository/order")
        result = route_cases_to_specs([outer, inner], [handler_case, repo_case])
        assert result[outer] == [handler_case]
        assert result[inner] == [repo_case]

    def test_どのプレフィクスにも前方一致しない由来があるときValueErrorになる(self):
        outer = SectionSpec("外", "svc", "go-json", Path("r.json"), ("pkg/handler",))
        with pytest.raises(ValueError):
            route_cases_to_specs([outer], [BehaviorCase((), "x", False, "pkg/other")])

    def test_複数のプレフィクスに前方一致する由来はより長いプレフィクスのセクションに入る(self):
        outer = SectionSpec("外", "svc", "go-json", Path("r.json"), ("pkg",))
        inner = SectionSpec("内", "svc", "go-json", Path("r.json"), ("pkg/repo",))
        repo_case = BehaviorCase((), "内のケース", False, "pkg/repo/order")
        root_case = BehaviorCase((), "外のケース", False, "pkg/handler/order")
        result = route_cases_to_specs([outer, inner], [repo_case, root_case])
        assert result[outer] == [root_case]
        assert result[inner] == [repo_case]

    def test_同じ長さのプレフィクスが複数のセクションに並ぶ由来があるときValueErrorになる(self):
        outer = SectionSpec("外", "svc", "go-json", Path("r.json"), ("pkg/repo",))
        inner = SectionSpec("内", "svc", "go-json", Path("r.json"), ("pkg/repo",))
        with pytest.raises(ValueError, match="同じ長さで振り分けられる"):
            route_cases_to_specs([outer, inner], [BehaviorCase((), "x", False, "pkg/repo/order")])


class Testセクションの組み立て:
    def test_形式ごとのパーサで結果を読みカテゴリの初出順にまとめる(self, tmp_path: Path):
        go = _write(
            tmp_path / "go.json",
            json.dumps({"Action": "pass", "Package": "pkg", "Test": "TestX/対象/Goのケース"}),
        )
        vitest = _write(
            tmp_path / "vitest.json",
            json.dumps({"testResults": [{"name": "f.test.ts", "assertionResults": [
                {"ancestorTitles": ["対象"], "title": "TSのケース", "status": "passed"}]}]}),
        )
        specs = [
            SectionSpec("外", "svc-go", "go-json", go, None),
            SectionSpec("外", "svc-ts", "vitest-json", vitest, None),
        ]
        sections = build_sections(specs)
        assert [(cat, label) for cat, label, _ in sections] == [("外", "svc-go"), ("外", "svc-ts")]
        assert [
            c.case_name for c in sections[0][2].subgroups["その他"].subgroups["対象"].cases
        ] == ["Goのケース"]
        assert [
            c.case_name for c in sections[1][2].subgroups["その他"].subgroups["対象"].cases
        ] == ["TSのケース"]

    def test_同じ結果ファイルに複数の形式が指定されたときValueErrorになる(self, tmp_path: Path):
        path = _write(tmp_path / "r.json", "[]")
        specs = [
            SectionSpec("外", "a", "go-json", path, ("x",)),
            SectionSpec("内", "a", "vitest-json", path, ("y",)),
        ]
        with pytest.raises(ValueError):
            build_sections(specs)


class TestMarkdownの描画:
    def test_射程の注意書きが引用として入る(self):
        output = render_markdown([], commit=None, title="カタログの表題")
        assert "> 本カタログは" in output

    def test_渡した表題が最上位の見出しになる(self):
        output = render_markdown([], commit=None, title="shop テスト観点カタログ")
        assert "# shop テスト観点カタログ" in output

    def test_セクション見出しにケース総数が入る(self):
        tree = build_group_tree([
            BehaviorCase((), "ケースA", False, "s"),
            BehaviorCase(("対象",), "ケースB", False, "s"),
        ])
        output = render_markdown([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert "### svc（全 2 ケース）" in output

    def test_同じカテゴリが連続するときカテゴリ見出しは1回だけ入る(self):
        tree = build_group_tree([BehaviorCase((), "ケース", False, "s")])
        output = render_markdown(
            [("外から見た振る舞い", "a", tree), ("外から見た振る舞い", "b", tree)],
            commit=None,
            title="カタログの表題",
        )
        assert output.count("## 外から見た振る舞い") == 1

    def test_カテゴリが切り替わるとき新しいカテゴリ見出しが入る(self):
        tree = build_group_tree([BehaviorCase((), "ケース", False, "s")])
        output = render_markdown(
            [("外から見た振る舞い", "a", tree), ("内部の挙動", "b", tree)],
            commit=None,
            title="カタログの表題",
        )
        assert "## 外から見た振る舞い" in output
        assert "## 内部の挙動" in output

    def test_上位グループは見出しその下のグループとケースは箇条書きとして現れる(self):
        tree = build_group_tree([BehaviorCase(("[認証系]ログイン処理",), "ケースA", False, "s")])
        output = render_markdown([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert "#### 認証系" in output
        assert "- **ログイン処理**" in output
        assert "- ケースA" in output

    def test_skip中のケースには未検証の注記が付く(self):
        tree = build_group_tree([BehaviorCase((), "未実装のケース", True, "s")])
        output = render_markdown([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert "未実装のケース（skip 中のため未検証）" in output

    def test_ケース名の山括弧はタグと誤解釈されない形に変換される(self):
        tree = build_group_tree([BehaviorCase((), "<script> を含むケース", False, "s")])
        output = render_markdown([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert "&lt;script&gt;" in output

    def test_commitを渡すと生成元commitの行が入る(self):
        assert "生成元 commit: `abc123`" in render_markdown(
            [], commit="abc123", title="カタログの表題"
        )

    def test_commitを渡さないと生成元commitの行は入らない(self):
        assert "生成元 commit" not in render_markdown([], commit=None, title="カタログの表題")


class TestHTMLの描画:
    def test_日本語ページとして本文にケース名と注意書きが入る(self):
        tree = build_group_tree([BehaviorCase((), "ケースA", False, "s")])
        output = render_html([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert '<html lang="ja">' in output
        assert "ケースA" in output
        assert "本カタログは" in output

    def test_渡した表題がタブ名と最上位の見出しになる(self):
        output = render_html([], commit=None, title="shop テスト観点カタログ")
        assert "<title>shop テスト観点カタログ</title>" in output
        assert "<h1>shop テスト観点カタログ</h1>" in output

    def test_下位グループは折りたたみ可能なdetailsとしてケース数の注記付きで現れる(self):
        tree = build_group_tree([BehaviorCase(("対象",), "ケースA", False, "s")])
        output = render_html([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert "<details><summary>対象（全 1 ケース）</summary>" in output

    def test_skip中のケースには専用クラスと注記が付く(self):
        tree = build_group_tree([BehaviorCase((), "未実装のケース", True, "s")])
        output = render_html([("外から見た振る舞い", "svc", tree)], commit=None, title="カタログの表題")
        assert '<li class="skipped">未実装のケース（skip 中のため未検証）</li>' in output


class Test上位グループ見出しの並び順:
    def _tagged_tree(self) -> GroupNode:
        return build_group_tree([
            BehaviorCase(("[認証系]ログイン処理",), "ケース1", False, "s"),
            BehaviorCase(("[描画系]盤面の描画",), "ケース2", False, "s"),
        ])

    def _untagged_and_tagged_tree(self) -> GroupNode:
        return build_group_tree([
            BehaviorCase(("タグの無い対象",), "ケース1", False, "s"),
            BehaviorCase(("[描画系]盤面の描画",), "ケース2", False, "s"),
        ])

    def test_タグ見出しはMarkdownでタグ名順に並ぶ(self):
        output = render_markdown(
            [("外から見た振る舞い", "svc", self._tagged_tree())], commit=None, title="カタログの表題"
        )
        assert output.index("#### 描画系") < output.index("#### 認証系")

    def test_タグ見出しはHTMLでタグ名順に並ぶ(self):
        output = render_html(
            [("外から見た振る舞い", "svc", self._tagged_tree())], commit=None, title="カタログの表題"
        )
        assert output.index("<summary>描画系") < output.index("<summary>認証系")

    def test_その他の見出しはMarkdownで他のタグ見出しより後に出る(self):
        output = render_markdown(
            [("外から見た振る舞い", "svc", self._untagged_and_tagged_tree())],
            commit=None,
            title="カタログの表題",
        )
        assert output.index("#### 描画系") < output.index("#### その他")

    def test_その他の見出しはHTMLで他のタグ見出しより後に出る(self):
        output = render_html(
            [("外から見た振る舞い", "svc", self._untagged_and_tagged_tree())],
            commit=None,
            title="カタログの表題",
        )
        assert output.index("<summary>描画系") < output.index("<summary>その他")


class Testセクション引数のパース:
    def test_カテゴリとラベルと形式とパスに分解される(self):
        spec = parse_section_arg("外:svc:go-json:results/svc.json")
        assert (spec.category, spec.label, spec.fmt, spec.path) == ("外", "svc", "go-json", Path("results/svc.json"))
        assert spec.prefixes is None

    def test_プレフィクスをカンマ区切りで受け取る(self):
        spec = parse_section_arg("外:svc:go-json:results/svc.json:pkg/handler,pkg/usecase")
        assert spec.prefixes == ("pkg/handler", "pkg/usecase")

    def test_項目が4つ未満のときエラーになる(self):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_section_arg("外:svc:go-json")

    def test_未対応の形式のときエラーになる(self):
        with pytest.raises(argparse.ArgumentTypeError):
            parse_section_arg("外:svc:unknown-fmt:results/svc.json")
