-- Migration: clean up duplicate event_logs from both inconsistent source_id
-- formats AND logical duplicates from repeated mock data generation + import.
--
-- Root causes addressed by the companion code fixes:
--   1. seed_mock_data.py used raw source_ids → fixed to use cert-r42: prefix
--   2. generate_mock_data.py produced logically duplicate events (same
--      timestamp/user/device/event_type/resource with different UUIDs) →
--      fixed with dedup tracker in generator
--   3. import_mock_data.py did not check for existing logical duplicates →
--      fixed with pre-insert check
--   4. list_frontend_logs now uses DISTINCT ON as a last-resort guard
--
-- This migration cleans up existing duplicates. Safe to re-run (idempotent).

BEGIN;

-- 1. Remove alerts that reference duplicate event_logs (keep the oldest).
DELETE FROM alerts
WHERE event_log_id IN (
    SELECT id FROM event_logs e1
    WHERE EXISTS (
        SELECT 1 FROM event_logs e2
        WHERE e2.timestamp = e1.timestamp
          AND COALESCE(e2.user_id, '') = COALESCE(e1.user_id, '')
          AND COALESCE(e2.device_id, '') = COALESCE(e1.device_id, '')
          AND e2.event_type = e1.event_type
          AND COALESCE(e2.resource, '') = COALESCE(e1.resource, '')
          AND e2.id < e1.id
    )
);

-- 2. Remove duplicate event_logs, keeping the oldest (lowest id) for each
--    logical group: (timestamp, user_id, device_id, event_type, resource).
DELETE FROM event_logs e1
WHERE EXISTS (
    SELECT 1 FROM event_logs e2
    WHERE e2.timestamp = e1.timestamp
      AND COALESCE(e2.user_id, '') = COALESCE(e1.user_id, '')
      AND COALESCE(e2.device_id, '') = COALESCE(e1.device_id, '')
      AND e2.event_type = e1.event_type
      AND COALESCE(e2.resource, '') = COALESCE(e1.resource, '')
      AND e2.id < e1.id
);

COMMIT;

-- Verify: should return 0 rows.
-- SELECT timestamp, user_id, device_id, event_type, resource, COUNT(*) AS cnt
-- FROM event_logs
-- GROUP BY timestamp, user_id, device_id, event_type, resource
-- HAVING COUNT(*) > 1
-- ORDER BY cnt DESC;
