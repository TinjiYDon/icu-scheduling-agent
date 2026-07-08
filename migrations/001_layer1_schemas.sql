-- Layer 1 schema (P0) for icu_scheduling
CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS feat;
CREATE SCHEMA IF NOT EXISTS sim;
CREATE SCHEMA IF NOT EXISTS sched;
CREATE SCHEMA IF NOT EXISTS app;

GRANT USAGE ON SCHEMA staging, feat, sim, sched, app TO icu_dev;
GRANT ALL ON ALL TABLES IN SCHEMA staging, feat, sim, sched, app TO icu_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA staging GRANT ALL ON TABLES TO icu_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA feat GRANT ALL ON TABLES TO icu_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA sim GRANT ALL ON TABLES TO icu_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA sched GRANT ALL ON TABLES TO icu_dev;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON TABLES TO icu_dev;

CREATE TABLE IF NOT EXISTS feat.sofa_timeseries (
    stay_id     BIGINT NOT NULL,
    hour_index  INT NOT NULL,
    sofa_total  REAL,
    PRIMARY KEY (stay_id, hour_index)
);

CREATE TABLE IF NOT EXISTS feat.patient_priority (
    stay_id     BIGINT PRIMARY KEY,
    priority_weight REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS sched.assignments (
    id          SERIAL PRIMARY KEY,
    run_id      TEXT NOT NULL,
    stay_id     BIGINT,
    bed_id      INT,
    created_at  TIMESTAMPTZ DEFAULT now()
);
