"""generate_api_docs のテスト."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

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


class Test型定義のパース:
    def test_models定義から型とフィールドとjsonキーを抽出する(self):
        types = parse_types(SAMPLE_MODELS)
        assert "Player" in types
        assert "Setting" in types
        assert len(types["Player"].fields) == 3
        assert types["Player"].fields[0].json_key == "id"
        assert types["Player"].fields[2].json_key == "level"

    def test_モデル定義が空のmappingのとき型は1件も抽出されない(self):
        assert parse_types({}) == {}

    def test_filesが空リストのときも型は抽出されない(self):
        assert parse_types({"files": []}) == {}

    def test_typesの無いファイル定義からは型が抽出されない(self):
        assert parse_types({"files": [{"path": "x"}]}) == {}

    def test_fieldsの無い型はヘッダ行だけのテーブルになる(self):
        types = parse_types({"files": [{"types": [{"name": "Empty"}]}]})
        assert types["Empty"].fields == []
        md = generate_type_table(types["Empty"])
        assert md.split("\n") == [
            "| フィールド | 型 | JSON | 説明 |",
            "|---|---|---|---|",
        ]


class Test型テーブルのMarkdown生成:
    def test_型定義をヘッダ付きMarkdownテーブルに整形する(self):
        td = TypeDef("Player", [
            FieldDef("ID", "string", "id", "プレイヤーID"),
            FieldDef("Level", "int", "level", "レベル"),
        ])
        md = generate_type_table(td)
        lines = md.split("\n")
        assert lines[0] == "| フィールド | 型 | JSON | 説明 |"
        assert lines[1] == "|---|---|---|---|"
        assert "| `ID` | `string` | `id` | プレイヤーID |" in lines[2]

    def test_説明のパイプ文字をエスケープする(self):
        td = TypeDef("T", [FieldDef("F", "string", "f", "a|b")])
        md = generate_type_table(td)
        assert "a\\|b" in md


class Testドキュメントのマーカー更新:
    def test_マーカー間の型テーブルを更新する(self, tmp_path: Path):
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

    def test_add_markersで既存テーブルにマーカーを挿入する(self, tmp_path: Path):
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


class Testフィールド説明とJSONキーの有無:
    @pytest.mark.parametrize(
        ("field_def", "expected_row"),
        [
            pytest.param(
                {"name": "F", "type": "string", "json": "f", "comment": "プレイヤーID"},
                "| `F` | `string` | `f` | プレイヤーID |",
                id="docキーが無いときcommentキーの値が説明になる",
            ),
            pytest.param(
                {"name": "F", "type": "string", "json": "f", "doc": "正", "comment": "副"},
                "| `F` | `string` | `f` | 正 |",
                id="docとcommentが両方あるときdocの値が説明になる",
            ),
            pytest.param(
                {"name": "F", "type": "string", "json": "f"},
                "| `F` | `string` | `f` |  |",
                id="docもcommentも無いとき説明が空になる",
            ),
            pytest.param(
                {"name": "F", "type": "string"},
                "| `F` | `string` |  |  |",
                id="jsonキーが無いフィールドはJSON列が空になる",
            ),
        ],
    )
    def test_型テーブルの説明列とJSON列を組み立てる(self, field_def, expected_row):
        models = {"files": [{"types": [{"name": "T", "fields": [field_def]}]}]}
        types = parse_types(models)
        md = generate_type_table(types["T"])
        assert md.split("\n")[2] == expected_row


class Test入力ファイル不在時の停止:
    def test_モデル定義YAMLが存在しないときエラーで停止する(self, tmp_path: Path):
        models_file = tmp_path / "missing_models.yaml"
        doc_file = tmp_path / "API_REFERENCE.md"
        original = "# API Reference\n"
        doc_file.write_text(original, encoding="utf-8")

        with pytest.raises(SystemExit, match=re.escape(models_file.name)):
            run(models_file, doc_file)

        assert doc_file.read_text(encoding="utf-8") == original
