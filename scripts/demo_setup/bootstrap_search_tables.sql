-- Bootstrap SQL for the metadata-index (search) service tables that live
-- in the *central* PostgreSQL database (the same DB that holds `study`,
-- `series`, `hospital`).
--
-- Created 2026-04-25 to unblock dev-spec-portal-redesign FR-INF-1.
-- The search container ships an alembic step that *should* create these,
-- but the packaged image is missing `alembic.ini script_location`, which
-- makes `search-admin migrate up` exit non-zero. Until that image bug is
-- fixed (tracked separately) we bootstrap the three tables straight from
-- this DDL — derived 1:1 from `src/radivault_search/db/models.py` so the
-- ORM keeps working without surgery.
--
-- Tables created:
--   * buyer            (FR-INF-1, dev-spec §6.2)
--   * buyer_api_key    (FR-INF-1, dev-spec §6.2)
--   * search_audit     (FR-INF-1, dev-spec §6.2 — composite PK ready for
--                       pg_partman partitioning in v0.1.1)
--
-- Idempotency: every CREATE / ALTER uses IF NOT EXISTS so re-running this
-- file is a no-op once the tables exist. Default privileges are also
-- replayed safely (Postgres dedupes them).
--
-- Apply with:
--   docker exec -i radivault-postgres-1 psql -U central_app -d central \
--     < scripts/demo_setup/bootstrap_search_tables.sql
--
-- Prerequisites: scripts/demo_setup/bootstrap_search_roles.sql must have
-- run first (it provisions `search_admin` and `radivault_buyer_ro`).

BEGIN;

-- 1) buyer ------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS buyer (
    buyer_pk       BIGSERIAL PRIMARY KEY,
    buyer_id       VARCHAR        NOT NULL,
    name           VARCHAR        NOT NULL,
    contact_email  VARCHAR        NOT NULL,
    tier           VARCHAR        NOT NULL DEFAULT 'preview',
    scope_json     JSONB          NOT NULL DEFAULT '{}'::jsonb,
    note           VARCHAR,
    enrolled_at    TIMESTAMPTZ    NOT NULL DEFAULT now(),
    active         BOOLEAN        NOT NULL DEFAULT TRUE,
    CONSTRAINT uq_buyer_buyer_id UNIQUE (buyer_id)
);

CREATE INDEX IF NOT EXISTS idx_buyer_active ON buyer (active);

-- 2) buyer_api_key ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS buyer_api_key (
    key_pk             BIGSERIAL PRIMARY KEY,
    buyer_pk           BIGINT       NOT NULL REFERENCES buyer (buyer_pk),
    kid                VARCHAR      NOT NULL,
    token_hash         VARCHAR      NOT NULL,
    tier               VARCHAR      NOT NULL DEFAULT 'preview',
    rate_limit_qps     INTEGER,
    rate_limit_daily   INTEGER,
    scope_json         JSONB        NOT NULL DEFAULT '{}'::jsonb,
    issued_at          TIMESTAMPTZ  NOT NULL DEFAULT now(),
    expires_at         TIMESTAMPTZ,
    revoked_at         TIMESTAMPTZ,
    last_used_at       TIMESTAMPTZ,
    note               VARCHAR,
    CONSTRAINT uq_buyer_api_key_kid UNIQUE (kid)
);

CREATE INDEX IF NOT EXISTS idx_buyer_api_key_buyer_active
    ON buyer_api_key (buyer_pk);

-- 3) search_audit -----------------------------------------------------------
-- ORM uses a single-column PK on `audit_pk` for SQLite test compatibility,
-- but on PostgreSQL the canonical shape is the composite PK
-- `(audit_pk, created_at)` so the table is PARTITION BY RANGE-ready for
-- pg_partman (tracked in alembic 0002 in the search repo). We mirror that
-- canonical PG shape here.
CREATE TABLE IF NOT EXISTS search_audit (
    audit_pk           BIGSERIAL    NOT NULL,
    buyer_pk           BIGINT       NOT NULL REFERENCES buyer (buyer_pk),
    kid                VARCHAR      NOT NULL,
    endpoint           VARCHAR      NOT NULL,
    filter_sha256      CHAR(64),
    filter_json_sha256 CHAR(64),
    result_count       BIGINT,
    cache_hit          BOOLEAN      NOT NULL DEFAULT FALSE,
    status_code        INTEGER      NOT NULL,
    error_code         VARCHAR,
    latency_ms         INTEGER      NOT NULL,
    request_id         VARCHAR      NOT NULL,
    cursor_presence    BOOLEAN      NOT NULL DEFAULT FALSE,
    created_at         TIMESTAMPTZ  NOT NULL DEFAULT now(),
    PRIMARY KEY (audit_pk, created_at)
);

CREATE INDEX IF NOT EXISTS idx_search_audit_buyer_time
    ON search_audit (buyer_pk, created_at);

CREATE INDEX IF NOT EXISTS idx_search_audit_filter_sha
    ON search_audit (filter_sha256);

-- 4) Privileges -------------------------------------------------------------
-- search_admin owns/writes the rows; radivault_buyer_ro is strictly READ.
-- These run after the CREATE TABLEs because role-grants on a missing
-- relation would error out. Wrapped in DO blocks so missing roles do not
-- abort the transaction (unlikely in practice — bootstrap_search_roles.sql
-- creates them — but defensive).

DO $grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'search_admin') THEN
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON buyer            TO search_admin';
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON buyer_api_key    TO search_admin';
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON search_audit     TO search_admin';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE buyer_buyer_pk_seq          TO search_admin';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE buyer_api_key_key_pk_seq    TO search_admin';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE search_audit_audit_pk_seq   TO search_admin';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'radivault_buyer_ro') THEN
        EXECUTE 'GRANT SELECT ON buyer            TO radivault_buyer_ro';
        EXECUTE 'GRANT SELECT ON buyer_api_key    TO radivault_buyer_ro';
        EXECUTE 'GRANT SELECT ON search_audit     TO radivault_buyer_ro';
    END IF;
END
$grants$;

-- Default privileges for any *future* tables created by central_app — keep
-- the buyer-RO promise intact even after schema evolution.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT ON TABLES TO radivault_buyer_ro;

COMMIT;

-- Verification helper: list the three tables + their owners.
\echo
\echo '== bootstrap_search_tables.sql complete =='
\echo 'Verifying tables:'
SELECT table_name, table_type
  FROM information_schema.tables
 WHERE table_schema = 'public'
   AND table_name IN ('buyer', 'buyer_api_key', 'search_audit')
 ORDER BY table_name;
