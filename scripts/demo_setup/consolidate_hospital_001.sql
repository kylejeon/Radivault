-- consolidate_hospital_001.sql
--
-- Purpose: Reassign all seeded studies/patients from HOSP-002 (hospital_pk=2)
-- to HOSP-001 (hospital_pk=1) so that the multi-PACS demo narrative is
-- coherent — Orthanc-A holds 250 historical studies as HOSP-001, while
-- Orthanc-B starts empty and HOSP-002 ingests its first study live during
-- the demo via STOW.
--
-- Context: Initial seed naively split a single Orthanc instance's 250
-- studies across two hospitals at the DB level only. That broke the
-- "two hospitals, two PACS" story Kyle wants for the D-13 demo.
--
-- Safety:
--   * UPDATE only, no DELETE — uid_map / DICOM-SR objects untouched.
--   * Wrapped in a single transaction so partial failure rolls back.
--   * `hospital` row for HOSP-002 stays intact (region_pseudo=BUSAN-B);
--     it gets repopulated when the gateway-b daemon ingests live demo data.
--
-- Run (host shell):
--   docker exec -i radivault-postgres-1 \
--     psql -U central_app -d central < consolidate_hospital_001.sql
--
-- Verify expectation after run:
--   hospital_pk | studies   -> 1 | 250  (single row)
--   hospital_pk | patients  -> 1 | 250  (single row)

BEGIN;

UPDATE patient_pseudo SET hospital_pk = 1 WHERE hospital_pk = 2;
UPDATE study           SET hospital_pk = 1 WHERE hospital_pk = 2;

COMMIT;

-- Post-run verification (run separately to inspect):
-- SELECT hospital_pk, COUNT(*) AS studies  FROM study           GROUP BY hospital_pk ORDER BY hospital_pk;
-- SELECT hospital_pk, COUNT(*) AS patients FROM patient_pseudo  GROUP BY hospital_pk ORDER BY hospital_pk;
-- SELECT hospital_pk, hospital_id, name, region_pseudo FROM hospital ORDER BY hospital_pk;
