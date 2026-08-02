"""report_builder のテスト。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report_builder import (  # noqa: E402
    ReportResult,
    Failure,
    build_annotations,
    build_summary,
    escape_data,
    escape_property,
    extract_location,
    parse,
)


class TestJUnitXML解析:
    def test_通過失敗スキップエラーが混在するとき件数が集計される(self):
        xml = """<?xml version="1.0"?>
        <testsuites>
          <testsuite>
            <testcase classname="test_sample" name="成功する" />
            <testcase classname="test_sample" name="失敗する">
              <failure message="AssertionError: 期待値と異なる">
                test_sample.py:9: AssertionError
              </failure>
            </testcase>
            <testcase classname="test_sample" name="準備に失敗する">
              <error message="RuntimeError: 準備失敗">
                test_sample.py:20: RuntimeError
              </error>
            </testcase>
            <testcase classname="test_sample" name="スキップする">
              <skipped type="pytest.skip" message="probe" />
            </testcase>
          </testsuite>
        </testsuites>
        """

        result = parse(xml, "/repo")

        assert result.passed == 1
        assert result.failed == 2
        assert result.skipped == 1

    def test_失敗したテストがあるときテスト名とメッセージと相対パスの失敗位置を保持する(self):
        xml = """<?xml version="1.0"?>
        <testsuites>
          <testsuite>
            <testcase classname="test_sample" name="失敗する">
              <failure message="AssertionError: 期待値と異なる">def test_失敗する():
        &gt;       assert 1 == 2
        E       AssertionError: 期待値と異なる

        /repo/tests/test_sample.py:9: AssertionError</failure>
            </testcase>
          </testsuite>
        </testsuites>
        """

        result = parse(xml, "/repo")

        assert result.failures == [
            Failure(
                name="test_sample.失敗する",
                message="AssertionError: 期待値と異なる",
                file="tests/test_sample.py",
                line=9,
            )
        ]


class Test失敗位置の抽出:
    def test_トレースバックにfile行番号があるときワークスペース相対パスと行番号を返す(self):
        file, line = extract_location("...\n/repo/tests/test_sample.py:9: AssertionError", "/repo")

        assert file == "tests/test_sample.py"
        assert line == 9

    def test_トレースバックに失敗位置が無いとき相対パスも行番号も返さない(self):
        file, line = extract_location("予期しない例外が発生しました", "/repo")

        assert file is None
        assert line is None


class Testサマリ生成:
    def test_失敗が無いとき失敗したテストの一覧は出力されない(self):
        result = ReportResult(passed=3, failed=0, skipped=0, failures=[])

        summary = build_summary("単体テスト結果", result)

        assert "## 単体テスト結果" in summary
        assert "失敗したテスト" not in summary

    def test_失敗があるとき失敗したテストの名前一覧が出力される(self):
        result = ReportResult(
            passed=1,
            failed=1,
            skipped=0,
            failures=[Failure(name="test_sample.失敗する", message="msg", file="a.py", line=1)],
        )

        summary = build_summary("単体テスト結果", result)

        assert "失敗したテスト" in summary
        assert "- test_sample.失敗する" in summary


class Test注釈生成:
    def test_失敗位置がわかるときfileとlineを伴うerrorになる(self):
        result = ReportResult(
            passed=0,
            failed=1,
            skipped=0,
            failures=[Failure(name="test_sample.失敗する", message="期待値と異なる", file="tests/test_sample.py", line=9)],
        )

        annotations = build_annotations(result)

        assert annotations == ["::error file=tests/test_sample.py,line=9::test_sample.失敗する: 期待値と異なる"]

    def test_失敗位置がわからないときfileとlineを伴わないerrorになる(self):
        result = ReportResult(
            passed=0,
            failed=1,
            skipped=0,
            failures=[Failure(name="test_sample.失敗する", message="予期しない例外", file=None, line=None)],
        )

        annotations = build_annotations(result)

        assert annotations == ["::error::test_sample.失敗する: 予期しない例外"]


class Testworkflowコマンド本文エスケープ:
    def test_パーセント記号を含むときパーセント25に置換される(self):
        assert escape_data("100%失敗") == "100%25失敗"

    def test_復帰文字を含むときパーセント0Dに置換される(self):
        assert escape_data("1行目\r2行目") == "1行目%0D2行目"

    def test_改行文字を含むときパーセント0Aに置換される(self):
        assert escape_data("1行目\n2行目") == "1行目%0A2行目"


class Testworkflowコマンドプロパティエスケープ:
    def test_コロンを含むときパーセント3Aに置換される(self):
        assert escape_property("tests/test_sample.py:9") == "tests/test_sample.py%3A9"

    def test_カンマを含むときパーセント2Cに置換される(self):
        assert escape_property("a,b.py") == "a%2Cb.py"
