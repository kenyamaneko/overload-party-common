-- Overload Party - PostgreSQL DDL (shared schema SSoT)
--
-- 各サービスが自スキーマを所有し、他サービスは API 経由で参照する。
-- スキーマ越境 FK はアプリ層整合性に委ねて張らない。
--
-- このファイルは shared スキーマのみを所有する。
-- per-service schemas は各サービスリポジトリの db/schema.sql が SSoT。
--
-- Per-service schemas (owned elsewhere):
--   account  : overload-party-account/db/schema.sql
--   card     : overload-party-card/db/schema.sql
--   shop     : overload-party-shop/db/schema.sql
--   scenario : overload-party-scenario/db/schema.sql
--   battle   : overload-party-battle/db/schema.sql
--   newsfeed : overload-party-newsfeed/db/schema.sql

-- =============================================================================
-- Shared schema
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS shared;

-- Shared: updated_at auto-update trigger function (referenced by
-- per-service schemas via `shared.update_updated_at`; keep this name stable).

CREATE OR REPLACE FUNCTION shared.update_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- Game Configuration (schema: shared, server-side KV store, read-only for all services)
-- =============================================================================

CREATE TABLE shared.game_config (
  key        VARCHAR(100) PRIMARY KEY,               -- 設定キー
  value      JSONB NOT NULL,                         -- 設定値
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now()      -- 更新日時
);
CREATE TRIGGER trg_game_config_updated_at BEFORE UPDATE ON shared.game_config FOR EACH ROW EXECUTE FUNCTION shared.update_updated_at();
