"""go_format のユニットテスト."""

import pytest

from codegen_tools.go_format import format_go_source


class TestGoソースの整形:
    def test_構造体タグが揃っていないとき整形して揃える(self) -> None:
        source = (
            "package apifoo\n"
            "\n"
            "type Foo struct {\n"
            "\tID string `json:\"id\"`\n"
            "\tLongerName string `json:\"longer_name\"`\n"
            "}\n"
        )

        formatted = format_go_source(source)

        assert '\tID         string `json:"id"`\n' in formatted
        assert '\tLongerName string `json:"longer_name"`\n' in formatted

    def test_末尾に空行があるとき取り除く(self) -> None:
        source = "package apifoo\n\ntype Foo struct{}\n\n"

        formatted = format_go_source(source)

        assert formatted.endswith("type Foo struct{}\n")

    def test_構文として成立しないソースのときエラーになる(self) -> None:
        with pytest.raises(ValueError, match="gofmt rejected"):
            format_go_source("package apifoo\n\ntype Foo struct {\n")
