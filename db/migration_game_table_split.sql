-- Migration: games テーブルの責務分離
-- See: docs/handoff/game-result-persistence.md
--
-- 本番未稼働のため破壊的変更として実行する。
-- psqldef を使う場合は schema_postgres.sql を直接適用すればよい。
-- このファイルは手動適用や差分確認用のリファレンス。

BEGIN;

-- =============================================================================
-- 1. 新テーブル作成
-- =============================================================================

CREATE TABLE IF NOT EXISTS game_npcs (
  game_id       VARCHAR(26) NOT NULL REFERENCES games(game_id),
  player_num    SMALLINT NOT NULL,
  npc_model     VARCHAR NOT NULL,
  PRIMARY KEY (game_id, player_num)
);

CREATE TABLE IF NOT EXISTS game_decks (
  game_id        VARCHAR(26) NOT NULL REFERENCES games(game_id),
  player_num     SMALLINT NOT NULL,
  deck_snapshot  JSONB NOT NULL,
  PRIMARY KEY (game_id, player_num)
);

CREATE TABLE IF NOT EXISTS game_players (
  game_id       VARCHAR(26) NOT NULL REFERENCES games(game_id),
  player_num    SMALLINT NOT NULL,
  player_id     UUID NOT NULL,
  PRIMARY KEY (game_id, player_num)
);

CREATE INDEX IF NOT EXISTS idx_game_players_player_id ON game_players(player_id);

-- =============================================================================
-- 2. games テーブル変更
-- =============================================================================

-- 新カラム追加
ALTER TABLE games ADD COLUMN IF NOT EXISTS first_player SMALLINT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS winning_player_num SMALLINT;
ALTER TABLE games ADD COLUMN IF NOT EXISTS win_reason TEXT;

-- 既存データがある場合のデフォルト設定（first_player は NOT NULL にするため）
UPDATE games SET first_player = 1 WHERE first_player IS NULL;
ALTER TABLE games ALTER COLUMN first_player SET NOT NULL;

-- 旧カラム削除
ALTER TABLE games DROP COLUMN IF EXISTS player1_id;
ALTER TABLE games DROP COLUMN IF EXISTS player2_id;
ALTER TABLE games DROP COLUMN IF EXISTS player1_deck_snapshot;
ALTER TABLE games DROP COLUMN IF EXISTS player2_deck_snapshot;
ALTER TABLE games DROP COLUMN IF EXISTS winner_id;
ALTER TABLE games DROP COLUMN IF EXISTS npc1_model;
ALTER TABLE games DROP COLUMN IF EXISTS npc2_model;
ALTER TABLE games DROP COLUMN IF EXISTS winner_num;

-- =============================================================================
-- 3. game_actions: player_id → player_num
-- =============================================================================

ALTER TABLE game_actions ADD COLUMN IF NOT EXISTS player_num SMALLINT;
UPDATE game_actions SET player_num = 1 WHERE player_num IS NULL;
ALTER TABLE game_actions ALTER COLUMN player_num SET NOT NULL;
ALTER TABLE game_actions DROP COLUMN IF EXISTS player_id;

-- =============================================================================
-- 4. game_events: player_id → player_num
-- =============================================================================

ALTER TABLE game_events ADD COLUMN IF NOT EXISTS player_num SMALLINT;
ALTER TABLE game_events DROP COLUMN IF EXISTS player_id;

COMMIT;
