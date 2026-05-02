"""go_emitter の純粋関数群に対するユニットテスト."""

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


# ─── resolve_auto_imports ──────────────────────────────────


def test_resolve_auto_imports_detects_time_and_json() -> None:
    types = [
        {
            "name": "Foo",
            "fields": [
                {"name": "T", "type": "time.Time"},
                {"name": "R", "type": "json.RawMessage"},
                {"name": "S", "type": "string"},
            ],
        }
    ]
    style = GoStyle()
    assert resolve_auto_imports(types, style.import_patterns) == {
        "time",
        "encoding/json",
    }


def test_resolve_auto_imports_detects_civil() -> None:
    types = [{"name": "X", "fields": [{"name": "D", "type": "civil.Date"}]}]
    style = GoStyle()
    assert resolve_auto_imports(types, style.import_patterns) == {
        "cloud.google.com/go/civil",
    }


def test_resolve_auto_imports_empty() -> None:
    types = [{"name": "X", "fields": [{"name": "S", "type": "string"}]}]
    assert resolve_auto_imports(types, GoStyle().import_patterns) == set()


# ─── render_import_block ───────────────────────────────────


def test_render_import_block_empty() -> None:
    assert render_import_block(set(), GoStyle()) == []


def test_render_import_block_std_only() -> None:
    out = render_import_block({"time", "encoding/json"}, GoStyle())
    assert out == [
        "import (",
        '\t"encoding/json"',
        '\t"time"',
        ")",
        "",
    ]


def test_render_import_block_separates_std_and_external() -> None:
    out = render_import_block(
        {"time", "cloud.google.com/go/civil"}, GoStyle()
    )
    assert out == [
        "import (",
        '\t"time"',
        "",
        '\t"cloud.google.com/go/civil"',
        ")",
        "",
    ]


def test_render_import_block_inline_single_for_matchmaking() -> None:
    style = GoStyle(use_inline_single_import=True)
    assert render_import_block({"time"}, style) == ['import "time"', ""]


def test_render_import_block_inline_falls_back_to_block_when_multiple() -> None:
    style = GoStyle(use_inline_single_import=True)
    out = render_import_block({"time", "encoding/json"}, style)
    assert out[0] == "import ("
    assert out[-1] == ""


# ─── render_const_block ────────────────────────────────────


def test_render_const_block_shop_style() -> None:
    """shop/support: 型注釈なし, 文字列のみクォート."""
    style = GoConstStyle(type_annotation=False, quote_string_only=True)
    out = render_const_block(
        {"type": "string", "values": [{"name": "A", "value": "alpha"}]},
        style,
    )
    assert out == ["const (", '\tA = "alpha"', ")", ""]


def test_render_const_block_card_style() -> None:
    """card: 型注釈あり, 常にクォート."""
    style = GoConstStyle(type_annotation=True)
    out = render_const_block(
        {"type": "PassiveEffectType", "values": [{"name": "X", "value": "v"}]},
        style,
    )
    assert out == ["const (", '\tX PassiveEffectType = "v"', ")", ""]


def test_render_const_block_empty_values_skipped() -> None:
    assert render_const_block({"type": "string", "values": []}, GoConstStyle()) == []


def test_render_const_block_non_string_unquoted_when_quote_string_only() -> None:
    style = GoConstStyle(type_annotation=False, quote_string_only=True)
    out = render_const_block(
        {"type": "int64", "values": [{"name": "MaxN", "value": 42}]},
        style,
    )
    assert out == ["const (", "\tMaxN = 42", ")", ""]


# ─── render_type_aliases ───────────────────────────────────


def test_render_type_aliases() -> None:
    out = render_type_aliases([{"name": "ID", "base": "string"}])
    assert out == ["type ID = string", ""]


def test_render_type_aliases_empty_returns_no_lines() -> None:
    assert render_type_aliases([]) == []


# ─── render_struct ─────────────────────────────────────────


def test_render_struct_aligned_with_json_and_db_tags() -> None:
    style = GoStyle(field_align=True, tag_keys=("json", "db"))
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


def test_render_struct_unaligned_for_matchmaking() -> None:
    style = GoStyle(
        field_align=False,
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


def test_render_struct_no_tag_no_padding_after_type() -> None:
    """タグ無しのときは type の後ろに空白を残さない (shop の挙動)."""
    style = GoStyle(field_align=True)
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


def test_render_struct_inline_comment() -> None:
    style = GoStyle(field_align=True, field_comment_position="inline")
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


def test_render_struct_multiline_type_comment() -> None:
    style = GoStyle(type_comment_multiline=True)
    td = {
        "name": "X",
        "comment": "line1\n\nline3",
        "fields": [{"name": "F", "type": "string"}],
    }
    out = render_struct(td, style)
    assert out[:3] == ["// line1", "//", "// line3"]


def test_render_struct_emit_tags_override() -> None:
    """target 別 emit_tags で同じ field 定義から異なるタグ集合を出せる."""
    style = GoStyle(field_align=True, tag_keys=("json",))
    td = {
        "name": "X",
        "fields": [{"name": "F", "type": "string", "json": "f", "db": "f_col"}],
    }
    json_only = render_struct(td, style, emit_tags=("json",))
    db_only = render_struct(td, style, emit_tags=("db",))
    assert any('json:"f"' in line and "db:" not in line for line in json_only)
    assert any('db:"f_col"' in line and "json:" not in line for line in db_only)


# ─── render_go_file ────────────────────────────────────────


def test_render_go_file_basic() -> None:
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


def test_render_go_file_extra_imports_merged() -> None:
    out = render_go_file(
        package="foo",
        types=[{"name": "X", "fields": [{"name": "S", "type": "string"}]}],
        style=GoStyle(),
        extra_imports={"context"},
    )
    assert '"context"' in out


def test_render_go_file_trailing_blank_line_compat() -> None:
    out = render_go_file(
        package="foo",
        types=[{"name": "X", "fields": [{"name": "S", "type": "string"}]}],
        style=GoStyle(),
        trailing_blank_line=True,
    )
    assert out.endswith("}\n\n")


def test_render_go_file_constants_and_aliases() -> None:
    out = render_go_file(
        package="p",
        types=[],
        style=GoStyle(),
        type_aliases=[{"name": "ID", "base": "string"}],
        constants=[{"type": "string", "values": [{"name": "A", "value": "a"}]}],
    )
    assert "type ID = string" in out
    assert 'A = "a"' in out
