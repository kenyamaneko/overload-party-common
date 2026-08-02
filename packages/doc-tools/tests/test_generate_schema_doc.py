"""generate_schema_doc のテスト."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from doc_tools.generate_schema_doc import (
    Column,
    Table,
    convert_snake_to_pascal,
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

    def test_NOT_NULLの無いカラムはNullableがYesになる(self):
        sql = "CREATE TABLE t (\n    nickname TEXT, -- ニックネーム\n);\n"
        tables = parse_schema(sql)
        md = generate_table_md(tables["t"])
        assert "| `nickname` | TEXT | Yes | ニックネーム |" in md

    def test_PRIMARY_KEY指定のカラムはNOT_NULLが無くてもNullableがNoになる(self):
        sql = "CREATE TABLE t (\n    id UUID PRIMARY KEY, -- 主キー\n);\n"
        tables = parse_schema(sql)
        md = generate_table_md(tables["t"])
        assert "| `id` | UUID | No | 主キー |" in md

    def test_テーブルレベルのPRIMARY_KEY行はカラムとして抽出されない(self):
        sql = (
            "CREATE TABLE t (\n"
            "    a INTEGER NOT NULL, -- 列a\n"
            "    b INTEGER NOT NULL, -- 列b\n"
            "    PRIMARY KEY (a, b)\n"
            ");\n"
        )
        tables = parse_schema(sql)
        assert [c.name for c in tables["t"].columns] == ["a", "b"]

    @pytest.mark.parametrize(
        "constraint_line",
        [
            pytest.param("PRIMARY KEY (a)", id="PRIMARY KEY 制約行"),
            pytest.param("FOREIGN KEY (a) REFERENCES other(id)", id="FOREIGN KEY 制約行"),
            pytest.param("CHECK (a > 0)", id="CHECK 制約行"),
            pytest.param("CONSTRAINT t_a_check CHECK (a > 0)", id="CONSTRAINT 制約行"),
            pytest.param("UNIQUE (a)", id="UNIQUE 制約行"),
        ],
    )
    def test_テーブルレベルの制約行はカラムとして抽出されない(self, constraint_line):
        sql = f"CREATE TABLE t (\n    a INTEGER NOT NULL, -- 列a\n    {constraint_line}\n);\n"
        tables = parse_schema(sql)
        assert [c.name for c in tables["t"].columns] == ["a"]

    def test_CREATE_INDEXとCREATE_TRIGGERの文からカラムを抽出しない(self):
        sql = (
            "CREATE TABLE shared.game_config (\n"
            "    key TEXT NOT NULL, -- 設定キー\n"
            "    CREATE INDEX idx_game_config_key ON shared.game_config (key)\n"
            "    CREATE TRIGGER trg_game_config_updated BEFORE UPDATE ON shared.game_config\n"
            ");\n"
        )
        tables = parse_schema(sql)
        assert [c.name for c in tables["game_config"].columns] == ["key"]

    def test_空のSQLからはテーブルが1件も抽出されない(self):
        assert parse_schema("") == {}

    def test_CREATE_TABLE文を含まないSQLからもテーブルが抽出されない(self):
        assert parse_schema("-- このファイルにはテーブル定義が無い\n") == {}

    def test_制約行しか持たないテーブルがあるときエラーになる(self):
        sql = "CREATE TABLE t (\n    PRIMARY KEY (a)\n);\n"
        with pytest.raises(ValueError, match="no column found in CREATE TABLE t"):
            parse_schema(sql)

    def test_文末のセミコロンが無くパースできないCREATE_TABLEがあるときエラーになる(self):
        sql = "CREATE TABLE t (\n    a INTEGER NOT NULL -- 列a\n"
        with pytest.raises(ValueError, match="declares 1 tables but 0 were parsed"):
            parse_schema(sql)

    def test_スキーマ違いで同名のテーブルが2つあるときエラーになる(self):
        sql = (
            "CREATE TABLE shared.t (\n    a INTEGER NOT NULL -- 列a\n);\n"
            "CREATE TABLE account.t (\n    b INTEGER NOT NULL -- 列b\n);\n"
        )
        with pytest.raises(ValueError, match="declares 2 tables but 1 were parsed"):
            parse_schema(sql)

    def test_コメント中のCREATE_TABLEはテーブル数に数えない(self):
        sql = (
            "-- CREATE TABLE を説明するコメント\n"
            "CREATE TABLE t (\n    a INTEGER NOT NULL -- 列a\n);\n"
        )
        assert list(parse_schema(sql)) == ["t"]

    def test_TIMESTAMP_WITH_TIME_ZONE型は複数語のまま抽出される(self):
        sql = "CREATE TABLE t (\n    created_at TIMESTAMP WITH TIME ZONE NOT NULL -- 作成日時\n);\n"
        tables = parse_schema(sql)
        assert tables["t"].columns[0].col_type == "TIMESTAMP WITH TIME ZONE"

    def test_DOUBLE_PRECISION型は複数語のまま抽出される(self):
        sql = "CREATE TABLE t (\n    ratio DOUBLE PRECISION NOT NULL -- 比率\n);\n"
        tables = parse_schema(sql)
        assert tables["t"].columns[0].col_type == "DOUBLE PRECISION"


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


class Testマーカー挿入対象の検出:
    def test_複数のテーブルがあるとき全てのテーブルがマーカーで囲まれ内容が更新される(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")

        doc_file = tmp_path / "DATA_DESIGN.md"
        doc_file.write_text(
            "# Data Design\n\n"
            "**GameConfig** (`shared.game_config`)\n\n"
            "| カラム名 | 型 | Nullable | 説明 |\n"
            "|---|---|---|---|\n"
            "| `key` | TEXT | No | 設定キー |\n\n"
            "**Players** (`account.players`)\n\n"
            "| カラム名 | 型 | Nullable | 説明 |\n"
            "|---|---|---|---|\n"
            "| `id` | UUID | No | プレイヤーID |\n",
            encoding="utf-8",
        )

        run(sql_file, doc_file, do_add_markers=True)

        result = doc_file.read_text(encoding="utf-8")
        assert "<!-- BEGIN GENERATED: game_config -->" in result
        assert "<!-- END GENERATED: game_config -->" in result
        assert "<!-- BEGIN GENERATED: players -->" in result
        assert "<!-- END GENERATED: players -->" in result
        assert "| `key` | TEXT | No | 設定キー |" in result
        assert "| `display_name` | TEXT | No | 表示名 |" in result

    def test_DDLに無い表名のテーブルは囲まれない(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")

        doc_file = tmp_path / "DATA_DESIGN.md"
        doc_file.write_text(
            "# Data Design\n\n"
            "**GameConfig** (`shared.game_config`)\n\n"
            "| カラム名 | 型 | Nullable | 説明 |\n"
            "|---|---|---|---|\n"
            "| `key` | TEXT | No | 設定キー |\n\n"
            "**LegacyTable** (`shared.legacy_table`)\n\n"
            "| カラム名 | 型 | Nullable | 説明 |\n"
            "|---|---|---|---|\n"
            "| `legacy_key` | TEXT | No | 旧設定キー |\n",
            encoding="utf-8",
        )

        run(sql_file, doc_file, do_add_markers=True)

        result = doc_file.read_text(encoding="utf-8")
        assert result.count("<!-- BEGIN GENERATED:") == 1
        assert "<!-- BEGIN GENERATED: game_config -->" in result
        assert "| `legacy_key` | TEXT | No | 旧設定キー |" in result

    def test_囲む対象のテーブルが無いときエラーで停止し文書を残す(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")

        doc_file = tmp_path / "DATA_DESIGN.md"
        original = "# Data Design\n\n本文のみ。\n"
        doc_file.write_text(original, encoding="utf-8")

        with pytest.raises(SystemExit, match="no table to add markers to"):
            run(sql_file, doc_file, do_add_markers=True)

        assert doc_file.read_text(encoding="utf-8") == original


class Test入力ファイル不在時の停止:
    def test_スキーマSQLが存在しないときエラーで停止する(self, tmp_path: Path):
        sql_file = tmp_path / "missing_schema.sql"
        doc_file = tmp_path / "DATA_DESIGN.md"
        original = "# Data Design\n"
        doc_file.write_text(original, encoding="utf-8")

        with pytest.raises(SystemExit, match=re.escape(sql_file.name)):
            run(sql_file, doc_file)

        assert doc_file.read_text(encoding="utf-8") == original

    def test_ドキュメントが存在しないときエラーで停止する(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")
        doc_file = tmp_path / "missing_doc.md"

        with pytest.raises(SystemExit, match=re.escape(doc_file.name)):
            run(sql_file, doc_file)

        assert not doc_file.exists()

    def test_マーカー挿入指定時もドキュメントが存在しないときエラーで停止する(self, tmp_path: Path):
        sql_file = tmp_path / "schema.sql"
        sql_file.write_text(SAMPLE_SQL, encoding="utf-8")
        doc_file = tmp_path / "missing_doc.md"

        with pytest.raises(SystemExit, match=re.escape(doc_file.name)):
            run(sql_file, doc_file, do_add_markers=True)

        assert not doc_file.exists()


class TestPascalCaseへの変換:
    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            pytest.param("game_config", "GameConfig", id="スネークケースの game_config は GameConfig になる"),
            pytest.param("players", "Players", id="単語1つの players は Players になる"),
            pytest.param("", "", id="空文字は空文字になる"),
        ],
    )
    def test_テーブル名をPascalCaseに変換する(self, value, expected):
        assert convert_snake_to_pascal(value) == expected
