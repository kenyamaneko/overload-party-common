"""CodegenRunner 統合テスト."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from codegen_tools import CodegenRunner, GoStyle, GoTarget


def _write_yaml(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _two_section_yaml(yaml_path: Path) -> None:
    """pre_render_hook テスト用の 2 section fixture を書き出す."""
    _write_yaml(
        yaml_path,
        {
            "files": [
                {"name": "a", "target": "wire", "types": []},
                {"name": "b", "target": "wire", "types": []},
            ]
        },
    )


class Testターゲット指定によるファイル生成:
    def test_単一targetでpackageとjsonタグを持つファイルを生成する(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {
                        "name": "user",
                        "target": "wire",
                        "types": [
                            {
                                "name": "User",
                                "fields": [{"name": "ID", "type": "string", "json": "id"}],
                            }
                        ],
                    }
                ]
            },
        )

        out_dir = tmp_path / "out"
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(out_dir, "apifoo", emit_tags=("json",))},
            style=GoStyle(),
        )
        rc = runner.run()
        assert rc == 0
        out_file = out_dir / "user_gen.go"
        assert out_file.exists()
        content = out_file.read_text()
        assert "package apifoo" in content
        assert 'json:"id"' in content

    def test_targetsリストで複数targetのファイルを生成する(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {
                        "name": "evt",
                        "targets": ["wire", "domain"],
                        "types": [
                            {
                                "name": "E",
                                "fields": [{"name": "ID", "type": "string", "json": "id"}],
                            }
                        ],
                    }
                ]
            },
        )

        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={
                "wire": GoTarget(tmp_path / "wire", "apifoo", emit_tags=("json",)),
                "domain": GoTarget(tmp_path / "dom", "domain", emit_tags=("json",)),
            },
        )
        assert runner.run() == 0
        assert (tmp_path / "wire" / "evt_gen.go").exists()
        assert (tmp_path / "dom" / "evt_gen.go").exists()

    def test_all_targetsキーワードで単一指定を全targetにtag別展開する(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {
                        "name": "u",
                        "target": "both",
                        "types": [
                            {
                                "name": "U",
                                "fields": [
                                    {"name": "ID", "type": "string", "json": "id", "db": "id"}
                                ],
                            }
                        ],
                    }
                ]
            },
        )

        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={
                "api": GoTarget(tmp_path / "api", "apiu", emit_tags=("json",)),
                "domain": GoTarget(tmp_path / "dom", "domain", emit_tags=("db",)),
            },
            all_targets_keyword="both",
        )
        assert runner.run() == 0
        api_text = (tmp_path / "api" / "u_gen.go").read_text()
        dom_text = (tmp_path / "dom" / "u_gen.go").read_text()
        assert 'json:"id"' in api_text and "db:" not in api_text
        assert 'db:"id"' in dom_text and "json:" not in dom_text

    def test_出力先の指定が無いとき既定の出力先に書き出す(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {
                        "name": "x",
                        "types": [
                            {
                                "name": "X",
                                "fields": [{"name": "F", "type": "string", "json": "f"}],
                            }
                        ],
                    }
                ]
            },
        )
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"default": GoTarget(tmp_path / "out", "p", emit_tags=("json",))},
            default_target_key="default",
        )
        assert runner.run() == 0
        assert (tmp_path / "out" / "x_gen.go").exists()

    def test_constantsブロックをshopスタイルで出力する(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {
                        "name": "enum",
                        "target": "wire",
                        "constants": [
                            {
                                "type": "string",
                                "values": [{"name": "A", "value": "alpha"}],
                            }
                        ],
                        "types": [],
                    }
                ]
            },
        )
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(tmp_path / "out", "p")},
        )
        runner.style.const_style.should_quote_string_only = True  # shop-style
        assert runner.run() == 0
        text = (tmp_path / "out" / "enum_gen.go").read_text()
        assert 'A = "alpha"' in text

    def test_type_aliasesを生成ファイルにtype行として書き出す(self, tmp_path: Path) -> None:
        # emitter 単体では関数レベルまでしか見ないため、models.yaml → runner → 実ファイル の
        # 統合パスをここで固定する。
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {
                        "name": "ids",
                        "target": "wire",
                        "type_aliases": [
                            {"name": "PlayerID", "base": "string"},
                            {"name": "DeckID", "base": "int64"},
                        ],
                        "types": [],
                    }
                ]
            },
        )
        out_dir = tmp_path / "out"
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(out_dir, "apifoo")},
        )
        assert runner.run() == 0
        content = (out_dir / "ids_gen.go").read_text()
        assert "type PlayerID = string" in content
        assert "type DeckID = int64" in content


class Testモデル定義の不正検出:
    @pytest.mark.parametrize(
        ("files", "match"),
        [
            pytest.param(
                [{"name": "x", "target": "wire", "targets": ["wire"], "types": []}],
                "both",
                id="target と targets を両方指定するとエラーになる",
            ),
            pytest.param(
                [{"name": "x", "target": "nope", "types": []}],
                "unknown target",
                id="未知の target 名はエラーになる",
            ),
            pytest.param(
                [{"name": "x", "types": []}],
                "has no `target`",
                id="target フィールドが無いとエラーになる",
            ),
            pytest.param(
                [{"name": "x", "targets": [], "types": []}],
                "non-empty list",
                id="targets が空リストのとき非空リストを要求するエラーになる",
            ),
            pytest.param(
                [{"name": "x", "targets": "wire", "types": []}],
                "non-empty list",
                id="targets がリストでないときも同じエラーになる",
            ),
        ],
    )
    def test_不正なtarget指定でValueErrorになる(
        self, tmp_path: Path, files: list[dict], match: str
    ) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(yaml_path, {"files": files})
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(tmp_path / "out", "p")},
        )
        with pytest.raises(ValueError, match=match):
            runner.run()

    def test_名前の無いセクションがあるとき終了コード1と標準エラーで報告しファイルを出力しない(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {"name": "ok", "target": "wire", "types": []},
                    {"target": "wire", "types": []},  # name 欠落
                ]
            },
        )
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(tmp_path / "out", "p")},
        )
        # 深部の不透明な KeyError ではなく run() 入口で明示メッセージにして報告する。
        rc = runner.run()
        assert rc == 1
        err = capsys.readouterr().err
        assert "models.yaml" in err
        assert "section #2" in err
        assert "`name`" in err
        # fail-fast: 出力ファイルは 1 件も書かれない
        assert not (tmp_path / "out").exists()

    @pytest.mark.parametrize(
        "models_data",
        [
            pytest.param({"other": 1}, id="filesセクションが無いとき"),
            pytest.param({"files": []}, id="filesが空リストのとき"),
        ],
    )
    def test_生成するファイルの定義が無いか空のとき終了コード1と標準エラーで報告しファイルを出力しない(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str], models_data: dict
    ) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(yaml_path, models_data)
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(tmp_path / "out", "p")},
        )
        rc = runner.run()
        assert rc == 1
        err = capsys.readouterr().err
        assert "models.yaml" in err
        assert "`files:`" in err
        assert not (tmp_path / "out").exists()


class Testpre_render_hookの適用:
    def test_セクションと出力先の組ごとに前処理が1回ずつ適用される(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _write_yaml(
            yaml_path,
            {
                "files": [
                    {"name": "x", "targets": ["wire", "domain"], "types": []},
                ]
            },
        )
        calls: list[tuple[str, str]] = []

        def hook(section: dict, target_key: str) -> dict:
            calls.append((section["name"], target_key))
            return section

        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={
                "wire": GoTarget(tmp_path / "out/wire", "w"),
                "domain": GoTarget(tmp_path / "out/domain", "d"),
            },
            pre_render_hook=hook,
        )
        assert runner.run() == 0
        assert calls == [("x", "wire"), ("x", "domain")]

    def test_hook返り値のtypes注入が生成Goに反映される(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _two_section_yaml(yaml_path)

        def inject_types(section: dict, _target_key: str) -> dict:
            section = dict(section)
            section["types"] = [
                {"name": f"Injected{section['name'].upper()}", "fields": [
                    {"name": "ID", "type": "string", "json": "id"},
                ]},
            ]
            return section

        out_dir = tmp_path / "out"
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(out_dir, "p")},
            pre_render_hook=inject_types,
        )
        assert runner.run() == 0
        assert "type InjectedA struct" in (out_dir / "a_gen.go").read_text()
        assert "type InjectedB struct" in (out_dir / "b_gen.go").read_text()

    def test_hookがNoneを返すとTypeErrorでsection名付きで止める(self, tmp_path: Path) -> None:
        # 不透明な AttributeError で落とさず、壊れた section を名指しする TypeError にする。
        yaml_path = tmp_path / "models.yaml"
        _two_section_yaml(yaml_path)
        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(tmp_path / "out", "p")},
            pre_render_hook=lambda _section, _target: None,  # type: ignore[return-value, arg-type]
        )
        with pytest.raises(TypeError, match=r"pre_render_hook for section 'a'.*returned NoneType"):
            runner.run()

    def test_hook内の例外を握りつぶさず伝搬する(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "models.yaml"
        _two_section_yaml(yaml_path)

        class HookError(Exception):
            pass

        def hook(_section: dict, _target_key: str) -> dict:
            raise HookError("boom")

        runner = CodegenRunner(
            models_yaml=yaml_path,
            repo_root=tmp_path,
            targets={"wire": GoTarget(tmp_path / "out", "p")},
            pre_render_hook=hook,
        )
        with pytest.raises(HookError, match="boom"):
            runner.run()
