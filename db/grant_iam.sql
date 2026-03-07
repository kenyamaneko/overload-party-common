-- IAM database authentication (Cloud SQL Auth Proxy with --auto-iam-authn)
-- Grant permissions to IAM service account users.
-- The user name follows the format: <sa-name>@<project-id>.iam
--
-- This file is NOT managed by psqldef (which doesn't support DO $$ blocks).
-- Run separately after schema migration.

DO $$
BEGIN
  -- gateway service account (dev)
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-gateway@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA public TO "overload-party-gateway@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "overload-party-gateway@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-gateway@overload-party-dev.iam";
  END IF;

  -- battle service account (dev)
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-battle@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA public TO "overload-party-battle@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "overload-party-battle@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-battle@overload-party-dev.iam";
  END IF;

  -- newsfeed service account (dev)
  IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'overload-party-newsfeed@overload-party-dev.iam') THEN
    GRANT USAGE ON SCHEMA public TO "overload-party-newsfeed@overload-party-dev.iam";
    GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO "overload-party-newsfeed@overload-party-dev.iam";
    ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO "overload-party-newsfeed@overload-party-dev.iam";
  END IF;
END
$$;
