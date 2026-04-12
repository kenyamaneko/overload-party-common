"""generate_api_docs のテスト."""

from __future__ import annotations

from pathlib import Path

from doc_tools.generate_api_docs import (
    FieldDef,
    TypeDef,
    generate_type_table,
    parse_types,
    run,
)


SAMPLE_MODELS = {
    "files": [
        {
            "path": "model/player.go",
            "types": [
                {
                    "name": "Player",
                    "fields": [
                        {"name": "ID", "type": "string", "json": "id", "doc": "プレイヤーID"},
                        {"name": "DisplayName", "type": "string", "json": "display_name", "doc": "表示名"},
                        {"name": "Level", "type": "int", "json": "level,omitempty", "doc": "レベル"},
                    ],
                },
                {
                    "name": "Setting",
                    "fields": [
                        {"name": "Key", "type": "string", "json": "key", "doc": "設定キー"},
                        {"name": "Value", "type": "string", "json": "value", "doc": "設定値"},
                    ],
                },
            ],
        }
    ]
}


def test_parse_types():
    """models.yaml の型定義をパースできること。"""
    types = parse_types(SAMPLE_MODELS)
    assert "Player" in types
    assert "Setting" in types
    assert len(types["Player"].fields) == 3
    assert types["Player"].fields[0].json_key == "id"
    assert types["Player"].fields[2].json_key == "level"


def test_generate_type_table():
    """Markdown テーブル出力のフォーマットを確認。"""
    td = TypeDef("Player", [
        FieldDef("ID", "string", "id", "プレイヤーID"),
        FieldDef("Level", "int", "level", "レベル"),
    ])
    md = generate_type_table(td)
    lines = md.split("\n")
    assert lines[0] == "| フィールド | 型 | JSON | 説明 |"
    assert lines[1] == "|---|---|---|---|"
    assert "| `ID` | `string` | `id` | プレイヤーID |" in lines[2]


def test_generate_type_table_pipe_escape():
    """説明にパイプ文字が含まれる場合にエスケープされること。"""
    td = TypeDef("T", [FieldDef("F", "string", "f", "a|b")])
    md = generate_type_table(td)
    assert "a\\|b" in md


def test_run_updates_markers(tmp_path: Path):
    """run() がマーカー間の型テーブルを更新すること。"""
    models_file = tmp_path / "models.yaml"

    import yaml
    models_file.write_text(yaml.dump(SAMPLE_MODELS), encoding="utf-8")

    doc_file = tmp_path / "API_REFERENCE.md"
    doc_file.write_text(
        "# API Reference\n\n"
        "<!-- BEGIN GENERATED: Player -->\n"
        "old content\n"
        "<!-- END GENERATED: Player -->\n",
        encoding="utf-8",
    )

    run(models_file, doc_file)

    result = doc_file.read_text(encoding="utf-8")
    assert "| `ID` | `string` | `id` | プレイヤーID |" in result
    assert "old content" not in result


def test_run_add_markers(tmp_path: Path):
    """--add-markers で既存テーブルにマーカーが挿入されること。"""
    import yaml

    models_file = tmp_path / "models.yaml"
    models_file.write_text(yaml.dump(SAMPLE_MODELS), encoding="utf-8")

    doc_file = tmp_path / "API_REFERENCE.md"
    doc_file.write_text(
        "# API Reference\n\n"
        "### `Player`\n\n"
        "| フィールド | 型 | JSON | 説明 |\n"
        "|---|---|---|---|\n"
        "| `ID` | `string` | `id` | プレイヤーID |\n",
        encoding="utf-8",
    )

    run(models_file, doc_file, do_add_markers=True)

    result = doc_file.read_text(encoding="utf-8")
    assert "<!-- BEGIN GENERATED: Player -->" in result
    assert "<!-- END GENERATED: Player -->" in result
