-- Demo reset (soft). Drops transient order + audit rows but preserves
-- study / hospital / buyer rows so the reseed is fast (dev-spec §8.4).
-- Run via: psql ... -f truncate_demo.sql

BEGIN;

TRUNCATE TABLE
  search_audit,
  download_event,
  order_state_history,
  order_outbox,
  transfer_job_dead_letter,
  transfer_job,
  order_item,
  "order"
CASCADE;

-- study, hospital, buyer, buyer_api_key are preserved.

COMMIT;
