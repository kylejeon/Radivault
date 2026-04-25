-- bootstrap_buyer_auth.sql — buyer-auth feature slug
--
-- Created 2026-04-25 to unblock dev-spec-buyer-auth.md FR-AUTH-1..12.
--
-- Adds the email/password + Argon2id self-serve signup model on top of the
-- existing buyer + buyer_api_key tables (created by
-- ``bootstrap_search_tables.sql``).
--
-- Schema-reality note vs dev-spec §6.2:
-- The dev-spec mermaid ER uses ``TEXT buyer_pk`` (cuid2 prefixed). The
-- already-deployed schema (commit 1457eb3) instead uses ``BIGSERIAL
-- buyer_pk`` with a separate ``buyer_id VARCHAR`` for the public id. Since
-- the buyer rows already exist in production demo, we honour the deployed
-- shape — every FK in this file is ``BIGINT REFERENCES buyer(buyer_pk)``.
-- Functional equivalence with dev-spec is preserved; only the column type
-- of the FK changes.
--
-- Tables created (FR-AUTH-1..11):
--   * buyer_credentials       (signup/password/PIPA consents/session_version)
--   * email_verification_otp  (FR-AUTH-2 6-digit OTP, 10min TTL)
--   * password_reset_token    (FR-AUTH-6 32-byte token, 60min TTL)
--   * auth_session_event      (FR-AUTH-1..11 audit trail, 10 event types)
--
-- Existing tables altered:
--   * buyer            (+ display_name, intent, country, contact_phone)
--   * buyer_api_key    (+ label DEFAULT 'default')
--                      (last_used_at + revoked_at already exist)
--
-- Idempotency: every CREATE/ALTER uses IF NOT EXISTS. Re-running is a no-op.
--
-- Apply with:
--   docker exec -i radivault-postgres-1 psql -U central_app -d central \
--     < scripts/demo_setup/bootstrap_buyer_auth.sql
--
-- Prerequisites:
--   - bootstrap_search_roles.sql (provisions search_admin + radivault_buyer_ro)
--   - bootstrap_search_tables.sql (provisions buyer + buyer_api_key)

BEGIN;

-- 1) citext extension -------------------------------------------------------
-- Required for buyer_credentials.email UNIQUE case-insensitive constraint.
CREATE EXTENSION IF NOT EXISTS citext;

-- 2) buyer ALTER ------------------------------------------------------------
-- dev-spec §6.2.1 — extra columns for organization/intent/country.
-- ``organization`` is intentionally separate from the existing ``name``
-- column (which today stores the company name). We use ``display_name``
-- as the buyer's chosen display label inside the portal so we don't break
-- the existing search-admin CLI's ``--company`` flow.
ALTER TABLE buyer
    ADD COLUMN IF NOT EXISTS display_name   VARCHAR,
    ADD COLUMN IF NOT EXISTS intent         VARCHAR,
    ADD COLUMN IF NOT EXISTS country        VARCHAR,
    ADD COLUMN IF NOT EXISTS contact_phone  VARCHAR;

-- ``intent`` enum check is added separately so re-running doesn't fail when
-- the constraint already exists. PostgreSQL does not have ADD CONSTRAINT IF
-- NOT EXISTS, so we wrap it in a DO block.
DO $intent_check$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_buyer_intent'
    ) THEN
        EXECUTE 'ALTER TABLE buyer ADD CONSTRAINT ck_buyer_intent '
             || 'CHECK (intent IS NULL OR intent IN '
             || '(''research'',''commercial-ai'',''clinical-trial'',''other''))';
    END IF;
END
$intent_check$;

-- 3) buyer_api_key ALTER ----------------------------------------------------
-- last_used_at + revoked_at already exist (commit 1457eb3). Only the
-- ``label`` column is new (FR-AUTH-8 multi-key v0.2 prep, default 'default'
-- for v0.1 single-key model).
ALTER TABLE buyer_api_key
    ADD COLUMN IF NOT EXISTS label VARCHAR NOT NULL DEFAULT 'default';

-- 4) buyer_credentials (new) -----------------------------------------------
-- dev-spec §6.2.2.
CREATE TABLE IF NOT EXISTS buyer_credentials (
    buyer_pk                BIGINT       PRIMARY KEY REFERENCES buyer(buyer_pk) ON DELETE CASCADE,
    email                   CITEXT       NOT NULL UNIQUE,
    password_hash           TEXT         NOT NULL,                    -- $argon2id$v=19$m=19456,t=2,p=1$...
    email_verified_at       TIMESTAMPTZ  NULL,
    marketing_email_opt_in  BOOLEAN      NOT NULL DEFAULT FALSE,
    session_version         INTEGER      NOT NULL DEFAULT 1,          -- bumped on pw-change/account-delete
    pipa_consents           JSONB        NOT NULL DEFAULT '{}'::jsonb, -- {collectUse, thirdParty, crossBorder, marketing} timestamps
    consent_terms_version   VARCHAR      NOT NULL DEFAULT 'tos-v1.0;privacy-v1.0',
    deleted_at              TIMESTAMPTZ  NULL,                        -- soft delete; hard delete cron at +30d
    created_at              TIMESTAMPTZ  NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_buyer_credentials_email_active
    ON buyer_credentials (email)
    WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_buyer_credentials_deleted
    ON buyer_credentials (deleted_at)
    WHERE deleted_at IS NOT NULL;

-- 5) email_verification_otp (new) ------------------------------------------
-- dev-spec §6.2.4. 6-digit OTP, 10min TTL, 3 attempts.
CREATE TABLE IF NOT EXISTS email_verification_otp (
    id           BIGSERIAL    PRIMARY KEY,
    buyer_pk     BIGINT       NOT NULL REFERENCES buyer(buyer_pk) ON DELETE CASCADE,
    otp_hash     TEXT         NOT NULL,           -- SHA-256(otp + salt)
    expires_at   TIMESTAMPTZ  NOT NULL,
    attempts     INTEGER      NOT NULL DEFAULT 0,
    consumed_at  TIMESTAMPTZ  NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_otp_buyer_active
    ON email_verification_otp (buyer_pk, expires_at)
    WHERE consumed_at IS NULL;

-- 6) password_reset_token (new) --------------------------------------------
-- dev-spec §6.2.5. 32-byte base64url token, 60min TTL, 1-shot.
CREATE TABLE IF NOT EXISTS password_reset_token (
    id           BIGSERIAL    PRIMARY KEY,
    buyer_pk     BIGINT       NOT NULL REFERENCES buyer(buyer_pk) ON DELETE CASCADE,
    token_hash   TEXT         NOT NULL UNIQUE,    -- SHA-256(token)
    expires_at   TIMESTAMPTZ  NOT NULL,
    used_at      TIMESTAMPTZ  NULL,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_pwd_reset_active
    ON password_reset_token (buyer_pk, expires_at)
    WHERE used_at IS NULL;

-- 7) auth_session_event (new) ----------------------------------------------
-- dev-spec §6.2.6. 10 event types.
CREATE TABLE IF NOT EXISTS auth_session_event (
    id           BIGSERIAL    PRIMARY KEY,
    buyer_pk     BIGINT       NULL REFERENCES buyer(buyer_pk) ON DELETE SET NULL,
    event_type   VARCHAR      NOT NULL,
    ip           VARCHAR,
    user_agent   VARCHAR,
    metadata     JSONB,
    created_at   TIMESTAMPTZ  NOT NULL DEFAULT now()
);

DO $event_check$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'ck_auth_event_type'
    ) THEN
        EXECUTE 'ALTER TABLE auth_session_event ADD CONSTRAINT ck_auth_event_type '
             || 'CHECK (event_type IN ('
             || '''signup'',''signin'',''signout'',''signin_failed'','
             || '''email_verified'',''password_reset'','
             || '''api_key_rotated'',''api_key_revoked'','
             || '''marketing_pref_changed'',''account_deleted''))';
    END IF;
END
$event_check$;

CREATE INDEX IF NOT EXISTS idx_auth_event_buyer_time
    ON auth_session_event (buyer_pk, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_auth_event_type_time
    ON auth_session_event (event_type, created_at DESC);

-- 8) Privileges -------------------------------------------------------------
-- search_admin owns/writes (just like the existing buyer table). The
-- radivault_buyer_ro role gets SELECT on the audit table only — credentials
-- and tokens are write-only from that role's perspective (dev-spec §11.4).

DO $grants$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'search_admin') THEN
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON buyer_credentials       TO search_admin';
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON email_verification_otp  TO search_admin';
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON password_reset_token    TO search_admin';
        EXECUTE 'GRANT INSERT, UPDATE, DELETE, SELECT ON auth_session_event      TO search_admin';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE email_verification_otp_id_seq   TO search_admin';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE password_reset_token_id_seq     TO search_admin';
        EXECUTE 'GRANT USAGE, SELECT ON SEQUENCE auth_session_event_id_seq       TO search_admin';
    END IF;

    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'radivault_buyer_ro') THEN
        -- Audit-only read for the RO role. password_hash & otp_hash & token_hash
        -- are NOT exposed to RO, even though they are already hashed — the
        -- principle is that the RO role exists for analytics, not auth.
        EXECUTE 'GRANT SELECT ON auth_session_event TO radivault_buyer_ro';
    END IF;
END
$grants$;

COMMIT;

-- Verification helper.
\echo
\echo '== bootstrap_buyer_auth.sql complete =='
\echo 'Verifying tables:'
SELECT table_name
  FROM information_schema.tables
 WHERE table_schema = 'public'
   AND table_name IN ('buyer_credentials','email_verification_otp',
                      'password_reset_token','auth_session_event')
 ORDER BY table_name;
\echo
\echo 'Verifying buyer columns:'
SELECT column_name, data_type
  FROM information_schema.columns
 WHERE table_schema = 'public'
   AND table_name = 'buyer'
   AND column_name IN ('display_name','intent','country','contact_phone')
 ORDER BY column_name;
