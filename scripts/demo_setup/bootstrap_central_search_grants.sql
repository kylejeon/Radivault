-- bootstrap_central_search_grants.sql
--
-- Search service (Option A 결정, dev-spec-metadata-index.md L.991 정합)
-- 가 central DB 를 직접 조회할 수 있도록 SELECT 권한 부여.
--
-- 적용:
--   docker exec -i radivault-postgres-1 psql -U central_app -d central \
--     < scripts/demo_setup/bootstrap_central_search_grants.sql
--
-- buyer/buyer_api_key/search_audit 권한은 bootstrap_search_tables.sql 에서
-- 이미 부여됨. 본 파일은 central-ingest 가 만든 study/hospital/audit_* 에
-- buyer_ro 가 SELECT 만 할 수 있도록 추가.
--
-- search_admin 은 central-ingest 테이블을 쓰지 않으므로 추가 권한 없음.

-- READ-ONLY: search 가 buyer 검색 시 필요한 study/hospital/patient_pseudo
GRANT SELECT ON study           TO radivault_buyer_ro;
GRANT SELECT ON hospital        TO radivault_buyer_ro;
GRANT SELECT ON patient_pseudo  TO radivault_buyer_ro;

-- READ-ONLY: 감사 체인 노출 시 필요할 수 있는 테이블 (FR-HO-5 audit-chain-status)
GRANT SELECT ON audit_anchor       TO radivault_buyer_ro;
GRANT SELECT ON audit_ingest_event TO radivault_buyer_ro;
GRANT SELECT ON audit_daily_digest TO radivault_buyer_ro;

-- 신규 series/instance 테이블이 추가되면 자동 적용되도록 default privilege
ALTER DEFAULT PRIVILEGES IN SCHEMA public
  GRANT SELECT ON TABLES TO radivault_buyer_ro;

-- 결과 확인
SELECT grantee, privilege_type, table_name
FROM information_schema.role_table_grants
WHERE table_schema='public'
  AND grantee='radivault_buyer_ro'
ORDER BY table_name, privilege_type;
