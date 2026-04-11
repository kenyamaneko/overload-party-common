-- IAM database authentication (Cloud SQL Auth Proxy with --auto-iam-authn)
-- Grant permissions to IAM service account users per-schema.
-- The user name follows the format: <sa-name>@<project-id>.iam
--
-- Schema layout (ADR-014):
--   - 各サービスは自スキーマのみに RW 権限を持つ
--   - 全サービスが shared スキーマに read-only アクセスを持つ
--   - サービス間の参照は REST API 経由。DB 越境参照は行わない
--   - matchmaking は DB を使わない (Redis + Pub/Sub のみ)
--   - gateway も DB 直接アクセスを持たない。必要データは各サービス API から取得
--
-- This file is NOT managed by psqldef (which doesn't support DO $$ blocks).
-- Run separately after schema migration.

DO $$
BEGIN
  -- ---------------------------------------------------------------------------
  -- account service account (dev): account スキーマ RW + shared 読取
  -- ---------------------------------------------------------------------------
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-account@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA account TO "overload-party-account@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA account TO "overload-party-account@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA account GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-account@overload-party-dev.iam";

    GRANT USAGE ON SCHEMA shared TO "overload-party-account@overload-party-dev.iam";
    GRANT SELECT ON ALL TABLES IN SCHEMA shared TO "overload-party-account@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT SELECT ON TABLES TO "overload-party-account@overload-party-dev.iam";
  END IF;

  -- ---------------------------------------------------------------------------
  -- card service account (dev): card スキーマ RW + shared 読取
  -- ---------------------------------------------------------------------------
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-card@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA card TO "overload-party-card@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA card TO "overload-party-card@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA card GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-card@overload-party-dev.iam";

    GRANT USAGE ON SCHEMA shared TO "overload-party-card@overload-party-dev.iam";
    GRANT SELECT ON ALL TABLES IN SCHEMA shared TO "overload-party-card@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT SELECT ON TABLES TO "overload-party-card@overload-party-dev.iam";
  END IF;

  -- ---------------------------------------------------------------------------
  -- shop service account (dev): shop スキーマ RW + shared 読取
  -- ---------------------------------------------------------------------------
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-shop@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA shop TO "overload-party-shop@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA shop TO "overload-party-shop@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shop GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-shop@overload-party-dev.iam";

    GRANT USAGE ON SCHEMA shared TO "overload-party-shop@overload-party-dev.iam";
    GRANT SELECT ON ALL TABLES IN SCHEMA shared TO "overload-party-shop@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT SELECT ON TABLES TO "overload-party-shop@overload-party-dev.iam";
  END IF;

  -- ---------------------------------------------------------------------------
  -- scenario service account (dev): scenario スキーマ RW + shared 読取
  -- ---------------------------------------------------------------------------
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-scenario@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA scenario TO "overload-party-scenario@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA scenario TO "overload-party-scenario@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA scenario GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-scenario@overload-party-dev.iam";

    GRANT USAGE ON SCHEMA shared TO "overload-party-scenario@overload-party-dev.iam";
    GRANT SELECT ON ALL TABLES IN SCHEMA shared TO "overload-party-scenario@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT SELECT ON TABLES TO "overload-party-scenario@overload-party-dev.iam";
  END IF;

  -- ---------------------------------------------------------------------------
  -- battle service account (dev): battle スキーマ RW + shared 読取
  -- ---------------------------------------------------------------------------
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-battle@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA battle TO "overload-party-battle@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA battle TO "overload-party-battle@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA battle GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-battle@overload-party-dev.iam";

    GRANT USAGE ON SCHEMA shared TO "overload-party-battle@overload-party-dev.iam";
    GRANT SELECT ON ALL TABLES IN SCHEMA shared TO "overload-party-battle@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT SELECT ON TABLES TO "overload-party-battle@overload-party-dev.iam";
  END IF;

  -- ---------------------------------------------------------------------------
  -- newsfeed service account (dev): newsfeed スキーマ RW + shared 読取
  -- ---------------------------------------------------------------------------
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-newsfeed@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA newsfeed TO "overload-party-newsfeed@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA newsfeed TO "overload-party-newsfeed@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA newsfeed GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-newsfeed@overload-party-dev.iam";

    GRANT USAGE ON SCHEMA shared TO "overload-party-newsfeed@overload-party-dev.iam";
    GRANT SELECT ON ALL TABLES IN SCHEMA shared TO "overload-party-newsfeed@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA shared GRANT SELECT ON TABLES TO "overload-party-newsfeed@overload-party-dev.iam";
  END IF;

  -- ---------------------------------------------------------------------------
  -- gateway service account (dev): DB 直接アクセスなし。
  -- ADR-014 に従い、gateway は各サービス API 経由でデータを取得する設計。
  -- ロールが存在しても DB 権限は一切付与しない。
  -- ---------------------------------------------------------------------------

  -- ---------------------------------------------------------------------------
  -- matchmaking service account (dev): DB 使用なし (Redis + Pub/Sub のみ)
  -- ---------------------------------------------------------------------------
END
$$;
