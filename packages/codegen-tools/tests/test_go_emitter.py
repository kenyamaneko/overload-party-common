"""go_emitter の純粋関数群に対するユニットテスト."""

import pytest

from codegen_tools.go_emitter import (
    GoConstStyle,
    GoStyle,
    render_const_block,
    render_go_file,
    render_import_block,
    render_struct,
    render_type_aliases,
    resolve_auto_imports,
)


class Testimportの自動解決:
    @pytest.mark.parametrize(
        ("types", "expected"),
        [
            pytest.param(
                [
                    {
                        "name": "Foo",
                        "fields": [
                            {"name": "T", "type": "time.Time"},
                            {"name": "R", "type": "json.RawMessage"},
                            {"name": "S", "type": "string"},
                        ],
                    }
                ],
                {"time", "encoding/json"},
                id="time.Time と json.RawMessage を使う型から time と encoding/json を検出する",
            ),
            pytest.param(
                [{"name": "X", "fields": [{"name": "D", "type": "civil.Date"}]}],
                {"cloud.google.com/go/civil"},
                id="civil.Date を使う型から cloud.google.com/go/civil を検出する",
            ),
            pytest.param(
                [{"name": "X", "fields": [{"name": "S", "type": "string"}]}],
                set(),
                id="標準型のみの型は import なしになる",
            ),
        ],
    )
    def test_フィールド型からimportを解決する(self, types, expected) -> None:
        assert resolve_auto_imports(types, GoStyle().import_patterns) == expected


class Testimportブロックの生成:
    @pytest.mark.parametrize(
        ("imports", "expected"),
        [
            pytest.param(set(), [], id="import が無いとき空リストになる"),
            pytest.param(
                {"time", "encoding/json"},
                [
                    "import (",
                    '\t"encoding/json"',
                    '\t"time"',
                    ")",
                    "",
                ],
                id="標準ライブラリのみのときソートして import ブロックにする",
            ),
            pytest.param(
                {"time", "cloud.google.com/go/civil"},
                [
                    "import (",
                    '\t"time"',
                    "",
                    '\t"cloud.google.com/go/civil"',
                    ")",
                    "",
                ],
                id="標準と外部が混在するとき空行で区切る",
            ),
        ],
    )
    def test_import集合からブロックを組み立てる(self, imports, expected) -> None:
        assert render_import_block(imports, GoStyle()) == expected

    def test_inline指定で単一importなら一行importにする(self) -> None:
        style = GoStyle(should_inline_single_import=True)
        assert render_import_block({"time"}, style) == ['import "time"', ""]

    def test_inline指定でも複数importならブロックにフォールバックする(self) -> None:
        style = GoStyle(should_inline_single_import=True)
        out = render_import_block({"time", "encoding/json"}, style)
        assert out[0] == "import ("
        assert out[-1] == ""


class Testconstブロックの生成:
    def test_shopスタイルは型注釈なしで文字列のみクォートする(self) -> None:
        style = GoConstStyle(has_type_annotation=False, should_quote_string_only=True)
        out = render_const_block(
            {"type": "string", "values": [{"name": "A", "value": "alpha"}]},
            style,
        )
        assert out == ["const (", '\tA = "alpha"', ")", ""]

    def test_cardスタイルは型注釈ありで常にクォートする(self) -> None:
        style = GoConstStyle(has_type_annotation=True)
        out = render_const_block(
            {"type": "PassiveEffectType", "values": [{"name": "X", "value": "v"}]},
            style,
        )
        assert out == ["const (", '\tX PassiveEffectType = "v"', ")", ""]

    def test_値が空のconstブロックはスキップする(self) -> None:
        assert render_const_block({"type": "string", "values": []}, GoConstStyle()) == []

    def test_文字列のみクォート指定では非文字列値をクォートしない(self) -> None:
        style = GoConstStyle(has_type_annotation=False, should_quote_string_only=True)
        out = render_const_block(
            {"type": "int64", "values": [{"name": "MaxN", "value": 42}]},
            style,
        )
        assert out == ["const (", "\tMaxN = 42", ")", ""]


class Test型エイリアスの生成:
    def test_エイリアス定義をtype行に変換する(self) -> None:
        out = render_type_aliases([{"name": "ID", "base": "string"}])
        assert out == ["type ID = string", ""]

    def test_エイリアスが無ければ空リストになる(self) -> None:
        assert render_type_aliases([]) == []


class Test構造体の生成:
    def test_alignかつjsonとdbタグを揃えて構造体を出す(self) -> None:
        style = GoStyle(should_align_field=True, tag_keys=("json", "db"))
        td = {
            "name": "Foo",
            "fields": [
                {"name": "ID", "type": "string", "json": "id", "db": "id"},
                {"name": "Created", "type": "time.Time", "json": "created"},
            ],
        }
        out = render_struct(td, style)
        assert out == [
            "type Foo struct {",
            '\tID      string    `json:"id" db:"id"`',
            '\tCreated time.Time `json:"created"`',
            "}",
            "",
        ]

    def test_align無効でコメントを上付きにして構造体を出す(self) -> None:
        style = GoStyle(
            should_align_field=False,
            field_extra_tag_key="tag",
            field_comment_key="doc",
            field_comment_position="above",
        )
        td = {
            "name": "Foo",
            "fields": [
                {
                    "name": "PlayerID",
                    "type": "string",
                    "json": "playerId",
                    "tag": 'binding:"required"',
                    "doc": "Player UUID.",
                }
            ],
        }
        out = render_struct(td, style)
        assert out == [
            "type Foo struct {",
            "\t// Player UUID.",
            '\tPlayerID string `json:"playerId" binding:"required"`',
            "}",
            "",
        ]

    def test_タグ無しのとき型の後ろに空白を残さない(self) -> None:
        style = GoStyle(should_align_field=True)
        td = {
            "name": "X",
            "fields": [
                {"name": "Foo", "type": "int64"},
                {"name": "BarBaz", "type": "string"},
            ],
        }
        out = render_struct(td, style)
        # max name=6, max type=6; Foo gets pad to align type column
        assert out == [
            "type X struct {",
            "\tFoo    int64",
            "\tBarBaz string",
            "}",
            "",
        ]

    def test_インラインコメントをタグの後ろに出す(self) -> None:
        style = GoStyle(should_align_field=True, field_comment_position="inline")
        td = {
            "name": "X",
            "fields": [{"name": "F", "type": "string", "json": "f", "comment": "note"}],
        }
        out = render_struct(td, style)
        assert out == [
            "type X struct {",
            '\tF string `json:"f"` // note',
            "}",
            "",
        ]

    def test_複数行の型コメントを行ごとに出す(self) -> None:
        style = GoStyle(is_type_comment_multiline=True)
        td = {
            "name": "X",
            "comment": "line1\n\nline3",
            "fields": [{"name": "F", "type": "string"}],
        }
        out = render_struct(td, style)
        assert out[:3] == ["// line1", "//", "// line3"]

    def test_emit_tagsで同じfield定義から異なるタグ集合を出す(self) -> None:
        style = GoStyle(should_align_field=True, tag_keys=("json",))
        td = {
            "name": "X",
            "fields": [{"name": "F", "type": "string", "json": "f", "db": "f_col"}],
        }
        json_only = render_struct(td, style, emit_tags=("json",))
        db_only = render_struct(td, style, emit_tags=("db",))
        assert any('json:"f"' in line and "db:" not in line for line in json_only)
        assert any('db:"f_col"' in line and "json:" not in line for line in db_only)


class TestGoファイルの生成:
    def test_ヘッダとpackageとimportとstructで構成する(self) -> None:
        out = render_go_file(
            package="foo",
            types=[
                {"name": "X", "fields": [{"name": "T", "type": "time.Time", "json": "t"}]}
            ],
            style=GoStyle(),
        )
        assert out.startswith("// Code generated")
        assert "package foo" in out
        assert 'import (\n\t"time"\n)' in out
        assert 'T time.Time `json:"t"`' in out
        assert out.endswith("\n")

    def test_extra_importsを自動importにマージする(self) -> None:
        out = render_go_file(
            package="foo",
            types=[{"name": "X", "fields": [{"name": "S", "type": "string"}]}],
            style=GoStyle(),
            extra_imports={"context"},
        )
        assert '"context"' in out

    def test_has_trailing_blank_lineで末尾に空行を足す(self) -> None:
        out = render_go_file(
            package="foo",
            types=[{"name": "X", "fields": [{"name": "S", "type": "string"}]}],
            style=GoStyle(),
            has_trailing_blank_line=True,
        )
        assert out.endswith("}\n\n")

    def test_constantsとtype_aliasesをファイルに含める(self) -> None:
        out = render_go_file(
            package="p",
            types=[],
            style=GoStyle(),
            type_aliases=[{"name": "ID", "base": "string"}],
            constants=[{"type": "string", "values": [{"name": "A", "value": "a"}]}],
        )
        assert "type ID = string" in out
        assert 'A = "a"' in out
