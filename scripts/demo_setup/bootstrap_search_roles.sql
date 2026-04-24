-- Bootstrap SQL for docker-compose.search.yml + docker-compose.fulfillment.yml
-- DSN expectations. Applies against the shared postgres container that
-- docker-compose.central.yml brings up with POSTGRES_USER=central_app.
--
-- Created 2026-04-24 Session 16 after inject_all.sh surfaced role gap.
-- This is a TEMPORARY local-dev workaround. Long-term fix: migrate to
-- postgres /docker-entrypoint-initdb.d/ volume mount so these roles are
-- created on first container start (requires destroying central_pgdata
-- volume, so deferred to v0.1.1 after CEO demo).
--
-- Usage:
--   docker exec -i radivault-postgres-1 psql -U central_app -d postgres \
--     < scripts/demo_setup/bootstrap_search_roles.sql
--
-- Idempotent: safe to re-run.

-- 1) Create radivault_central database (distinct from `central` used by
--    central-ingest service).
SELECT 'CREATE DATABASE radivault_central'
 WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'radivault_central')
\gexec

-- 2) Create roles with matching credentials from docker-compose.search.yml
--    and docker-compose.fulfillment.yml. Password equals username per the
--    compose literals; demo-grade only, rotate for pilot.
DO $$
BEGIN
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'search_admin') THEN
    CREATE ROLE search_admin LOGIN PASSWORD 'search_admin';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'radivault_buyer_ro') THEN
    CREATE ROLE radivault_buyer_ro LOGIN PASSWORD 'radivault_buyer_ro';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'central_migrator') THEN
    CREATE ROLE central_migrator LOGIN PASSWORD 'central_migrator';
  END IF;
  IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = 'radivault_fulfillment_app') THEN
    CREATE ROLE radivault_fulfillment_app LOGIN PASSWORD 'radivault_fulfillment_app';
  END IF;
END
$$;

-- 3) Grant DB-level privileges on radivault_central.
GRANT ALL PRIVILEGES ON DATABASE radivault_central TO search_admin;
GRANT ALL PRIVILEGES ON DATABASE radivault_central TO central_migrator;
GRANT ALL PRIVILEGES ON DATABASE radivault_central TO radivault_fulfillment_app;
GRANT CONNECT ON DATABASE radivault_central TO radivault_buyer_ro;

-- 4) Schema-level grants executed inside target DB.
\connect radivault_central
GRANT USAGE, CREATE ON SCHEMA public TO search_admin, central_migrator, radivault_fulfillment_app;
GRANT USAGE ON SCHEMA public TO radivault_buyer_ro;

-- Default privileges so future tables created by search_admin are readable
-- by radivault_buyer_ro without manual GRANT.
ALTER DEFAULT PRIVILEGES FOR ROLE search_admin IN SCHEMA public
  GRANT SELECT ON TABLES TO radivault_buyer_ro;
ALTER DEFAULT PRIVILEGES FOR ROLE central_migrator IN SCHEMA public
  GRANT SELECT ON TABLES TO radivault_buyer_ro;
