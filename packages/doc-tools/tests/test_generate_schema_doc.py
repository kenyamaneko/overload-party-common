"""generate_schema_doc のテスト."""

from __future__ import annotations

from pathlib import Path

from doc_tools.generate_schema_doc import (
    Column,
    Table,
    generate_table_md,
    parse_schema,
    run,
)


SAMPLE_SQL = """\
CREATE TABLE shared.game_config (
    key   TEXT NOT NULL PRIMARY KEY, -- 設定キー
    value TEXT NOT NULL              -- 設定値
);

CREATE TABLE account.players (
    id         UUID NOT NULL PRIMARY KEY DEFAULT gen_random_uuid(), -- プレイヤーID
    display_name TEXT NOT NULL,                                     -- 表示名
    level      INTEGER NOT NULL DEFAULT 1,                          -- レベル
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()                   -- 作成日時
);
"""

SAMPLE_SQL_IF_NOT_EXISTS = """\
CREATE TABLE IF NOT EXISTS news_articles (
    id         BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY, -- 記事ID
    title      TEXT NOT NULL,                                    -- タイトル
    url        TEXT NOT NULL                                     -- URL
);
"""


class Testスキーマのパース:
    def test_基本的なCREATE_TABLEからテーブルとカラムを抽出する(self):
        tables = parse_schema(SAMPLE_SQL)
        assert "game_config" in tables
        assert "players" in tables
        assert len(tables["game_config"].columns) == 2
        assert len(tables["players"].columns) == 4

        key_col = tables["game_config"].columns[0]
        assert key_col.name == "key"
        assert key_col.col_type == "TEXT"
        assert key_col.is_nullable is False
        assert key_col.doc == "設定キー"

    def test_IF_NOT_EXISTS付きのCREATE_TABLEをパースする(self):
        tables = parse_schema(SAMPLE_SQL_IF_NOT_EXISTS)
        assert "news_articles" in tables
        tbl = tables["news_articles"]
        assert len(tbl.columns) == 3
        assert tbl.columns[0].name == "id"
        assert "(IDENTITY)" in tbl.columns[0].col_type

    def test_GENERATED_ALWAYS_AS_IDENTITYをIDENTITY表記にする(self):
        tables = parse_schema(SAMPLE_SQL_IF_NOT_EXISTS)
        id_col = tables["news_articles"].columns[0]
        assert id_col.col_type == "BIGINT (IDENTITY)"
        assert id_col.is_nullable is False


class Testテーブル定義のMarkdown生成:
    def test_テーブル定義をヘッダ付きMarkdownテーブルに整形する(self):
        tbl = Table("test_table", [
            Column("id", "UUID", False, "主キー"),
            Column("name", "TEXT", True, "名前"),
        ])
        md = generate_table_md(tbl)
        lines = md.split("\n")
        assert lines[0] == "| カラム名 | 型 | Nullable | 説明 |"
        assert lines[1] == "|---|---|---|---|"
        assert "| `id` | UUID | No | 主キー |" in lines[2]
        assert "| `name` | TEXT | Yes | 名前 |" in lines[3]

    def test_説明のパイプ文字をエスケープする(self):
        tbl = Table("t", [Column("c", "TEXT", True, "a|b")])
        md = generate_table_md(tbl)
        assert "a\\|b" in md


class Testドキュメントのマーカー更新:
    def test_マーカー間のテーブルを更新する(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")

        doc_file = tmp_path / "DATA_DESIGN.md"
        doc_file.write_text(
            "# Data Design\n\n"
            "<!-- BEGIN GENERATED: game_config -->\n"
            "old content\n"
            "<!-- END GENERATED: game_config -->\n",
            encoding="utf-8",
        )

        run(sql_file, doc_file)

        result = doc_file.read_text(encoding="utf-8")
        assert "| `key` | TEXT | No | 設定キー |" in result
        assert "| `value` | TEXT | No | 設定値 |" in result
        assert "old content" not in result

    def test_add_markersで既存テーブルにマーカーを挿入する(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")

        doc_file = tmp_path / "DATA_DESIGN.md"
        doc_file.write_text(
            "# Data Design\n\n"
            "**GameConfig** (`shared.game_config`)\n\n"
            "| カラム名 | 型 | Nullable | 説明 |\n"
            "|---|---|---|---|\n"
            "| `key` | TEXT | No | 設定キー |\n",
            encoding="utf-8",
        )

        run(sql_file, doc_file, do_add_markers=True)

        result = doc_file.read_text(encoding="utf-8")
        assert "<!-- BEGIN GENERATED: game_config -->" in result
        assert "<!-- END GENERATED: game_config -->" in result
