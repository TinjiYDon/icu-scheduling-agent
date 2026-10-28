-- Fix the misleading `staging.icustays.los_hours` name.
-- The column actually stores days (verified: 39.3h stay -> 1.64).
-- Keep the legacy column for compatibility and expose explicit units via a view.

CREATE OR REPLACE VIEW staging.icustays_v AS
SELECT
    stay_id,
    subject_id,
    hadm_id,
    first_careunit,
    last_careunit,
    intime,
    outtime,
    los_hours AS los_days,
    los_hours * 24.0 AS elapsed_hours
FROM staging.icustays;

COMMENT ON COLUMN staging.icustays.los_hours
    IS 'LEGACY NAME: stores days, not hours. Use staging.icustays_v.elapsed_hours.';
