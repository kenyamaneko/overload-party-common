"""Unit tests for generate_schema_doc.py — DDL parse → Markdown generation."""

from generate_schema_doc import Column, Table, parse_schema, generate_table_md


# ── parse_schema ──────────────────────────────────────────


class TestParseBasic:
    """基本的なカラム定義のパース."""

    SQL = """
    CREATE TABLE players (
      player_id  UUID NOT NULL DEFAULT gen_random_uuid(), -- UUID
      username   VARCHAR(50) NOT NULL,                    -- 表示名
      level      BIGINT NOT NULL DEFAULT 1,               -- レベル (Default: 1)
      bio        TEXT,                                    -- 自己紹介
      created_at TIMESTAMPTZ NOT NULL DEFAULT now(),      -- 作成日時
      PRIMARY KEY (player_id)
    );
    """

    def test_table_found(self):
        tables = parse_schema(self.SQL)
        assert "players" in tables

    def test_column_count(self):
        t = parse_schema(self.SQL)["players"]
        assert len(t.columns) == 5

    def test_not_null(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["players"].columns}
        assert cols["player_id"].nullable is False
        assert cols["username"].nullable is False

    def test_nullable(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["players"].columns}
        assert cols["bio"].nullable is True

    def test_type(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["players"].columns}
        assert cols["player_id"].col_type == "UUID"
        assert cols["username"].col_type == "VARCHAR(50)"
        assert cols["level"].col_type == "BIGINT"
        assert cols["created_at"].col_type == "TIMESTAMPTZ"

    def test_doc(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["players"].columns}
        assert cols["player_id"].doc == "UUID"
        assert cols["username"].doc == "表示名"
        assert cols["level"].doc == "レベル (Default: 1)"


class TestParseIdentity:
    """GENERATED ALWAYS AS IDENTITY の扱い."""

    SQL = """
    CREATE TABLE decks (
      player_id UUID NOT NULL,                              -- 親テーブル参照
      deck_id   BIGINT NOT NULL GENERATED ALWAYS AS IDENTITY, -- デッキID（自動採番）
      PRIMARY KEY (player_id, deck_id)
    );
    """

    def test_identity_type(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["decks"].columns}
        assert cols["deck_id"].col_type == "BIGINT (IDENTITY)"
        assert cols["deck_id"].nullable is False


class TestParsePrimaryKeyInline:
    """カラム定義に PRIMARY KEY が直接書かれている場合."""

    SQL = """
    CREATE TABLE game_config (
      key   VARCHAR(100) PRIMARY KEY,  -- 設定キー
      value JSONB NOT NULL             -- 設定値
    );
    """

    def test_pk_implies_not_null(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["game_config"].columns}
        assert cols["key"].nullable is False
        assert cols["key"].col_type == "VARCHAR(100)"


class TestParseReferencesInline:
    """カラム定義に REFERENCES が直接書かれている場合."""

    SQL = """
    CREATE TABLE game_states (
      game_id VARCHAR(26) PRIMARY KEY REFERENCES games(game_id) ON DELETE CASCADE, -- 親テーブル参照
      version BIGINT NOT NULL -- バージョン
    );
    """

    def test_references_stripped_from_type(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["game_states"].columns}
        assert cols["game_id"].col_type == "VARCHAR(26)"
        assert cols["game_id"].nullable is False


class TestParseCheck:
    """CHECK 制約付きカラムのパース."""

    SQL = """
    CREATE TABLE player_factions (
      player_id UUID NOT NULL,                                                      -- 親テーブル参照
      faction   VARCHAR(20) NOT NULL CHECK (faction IN ('SHE', 'Tenki', 'Sugar')),  -- 陣営名
      PRIMARY KEY (player_id, faction)
    );
    """

    def test_check_stripped_from_type(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["player_factions"].columns}
        assert cols["faction"].col_type == "VARCHAR(20)"
        assert cols["faction"].nullable is False
        assert cols["faction"].doc == "陣営名"


class TestParseArray:
    """TEXT[] 型のパース."""

    SQL = """
    CREATE TABLE episodes (
      id    VARCHAR(50) NOT NULL,                   -- ID
      tags  TEXT[] NOT NULL DEFAULT '{}',            -- タグ
      PRIMARY KEY (id)
    );
    """

    def test_array_type(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["episodes"].columns}
        assert cols["tags"].col_type == "TEXT[]"


class TestParseNoComment:
    """インラインコメントがないカラムは doc が空文字."""

    SQL = """
    CREATE TABLE minimal (
      id   INT NOT NULL,
      name TEXT,
      PRIMARY KEY (id)
    );
    """

    def test_empty_doc(self):
        cols = {c.name: c for c in parse_schema(self.SQL)["minimal"].columns}
        assert cols["id"].doc == ""
        assert cols["name"].doc == ""


class TestParseSkipsConstraints:
    """PRIMARY KEY / FOREIGN KEY 行はカラムとしてパースしない."""

    SQL = """
    CREATE TABLE deck_cards (
      player_id UUID NOT NULL,     -- ルート親参照
      deck_id   BIGINT NOT NULL,   -- 親テーブル参照
      card_id   VARCHAR(10) NOT NULL, -- カード識別子
      PRIMARY KEY (player_id, deck_id, card_id),
      FOREIGN KEY (player_id, deck_id) REFERENCES decks(player_id, deck_id) ON DELETE CASCADE
    );
    """

    def test_only_columns(self):
        t = parse_schema(self.SQL)["deck_cards"]
        names = [c.name for c in t.columns]
        assert names == ["player_id", "deck_id", "card_id"]


class TestParseMultipleTables:
    """複数テーブルを一括パース."""

    SQL = """
    CREATE TABLE a (
      id INT NOT NULL,
      PRIMARY KEY (id)
    );
    CREATE TABLE b (
      id   INT NOT NULL,
      name TEXT,
      PRIMARY KEY (id)
    );
    """

    def test_both_found(self):
        tables = parse_schema(self.SQL)
        assert len(tables) == 2
        assert "a" in tables and "b" in tables

    def test_column_counts(self):
        tables = parse_schema(self.SQL)
        assert len(tables["a"].columns) == 1
        assert len(tables["b"].columns) == 2


# ── generate_table_md ─────────────────────────────────────


class TestGenerateTableMd:
    """Markdown テーブル文字列の生成."""

    def test_basic(self):
        t = Table("test", [
            Column("id", "UUID", False, "主キー"),
            Column("name", "VARCHAR(50)", False, "名前"),
            Column("bio", "TEXT", True, "自己紹介"),
        ])
        md = generate_table_md(t)
        lines = md.split("\n")
        assert lines[0] == "| カラム名 | 型 | Nullable | 説明 |"
        assert lines[1] == "|---|---|---|---|"
        assert lines[2] == "| `id` | UUID | No | 主キー |"
        assert lines[3] == "| `name` | VARCHAR(50) | No | 名前 |"
        assert lines[4] == "| `bio` | TEXT | Yes | 自己紹介 |"
        assert len(lines) == 5

    def test_pipe_escaped(self):
        t = Table("test", [
            Column("status", "VARCHAR(20)", False, "'a' | 'b' | 'c'"),
        ])
        md = generate_table_md(t)
        data_line = md.split("\n")[2]
        assert "\\|" in data_line
        assert "'a' \\| 'b' \\| 'c'" in data_line


class TestEndToEnd:
    """SQL → parse → generate の結合テスト."""

    SQL = """
    CREATE TABLE products (
      product_id VARCHAR(50) NOT NULL,    -- 商品ID
      name       VARCHAR(100) NOT NULL,   -- 商品名
      price      BIGINT NOT NULL,         -- 価格 (JPY)
      is_active  BOOLEAN NOT NULL,        -- 販売中フラグ
      memo       TEXT,                    -- メモ
      PRIMARY KEY (product_id)
    );
    """

    def test_full_pipeline(self):
        tables = parse_schema(self.SQL)
        md = generate_table_md(tables["products"])
        lines = md.split("\n")

        assert len(lines) == 7  # header + separator + 5 columns
        assert "| `product_id` | VARCHAR(50) | No | 商品ID |" in lines
        assert "| `price` | BIGINT | No | 価格 (JPY) |" in lines
        assert "| `memo` | TEXT | Yes | メモ |" in lines
