-- H=1 rolling decision audit trail.
CREATE TABLE IF NOT EXISTS sched.rolling_runs (
    run_id      TEXT PRIMARY KEY,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    status      TEXT NOT NULL DEFAULT 'running',
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    summary     JSONB
);

CREATE TABLE IF NOT EXISTS sched.rolling_decisions (
    run_id                TEXT NOT NULL
                          REFERENCES sched.rolling_runs(run_id) ON DELETE CASCADE,
    step                  INT NOT NULL,
    hour                  INT NOT NULL,
    status                TEXT NOT NULL,
    assignments           JSONB NOT NULL DEFAULT '{}'::jsonb,
    top_assignments       JSONB NOT NULL DEFAULT '[]'::jsonb,
    waiting               JSONB NOT NULL DEFAULT '[]'::jsonb,
    pending               JSONB NOT NULL DEFAULT '[]'::jsonb,
    discharged            JSONB NOT NULL DEFAULT '[]'::jsonb,
    transferred           JSONB NOT NULL DEFAULT '[]'::jsonb,
    warded                JSONB NOT NULL DEFAULT '[]'::jsonb,
    ward_census           INT NOT NULL DEFAULT 0,
    arrivals              JSONB NOT NULL DEFAULT '[]'::jsonb,
    departed               JSONB NOT NULL DEFAULT '[]'::jsonb,
    patient_conservation  BOOLEAN NOT NULL,
    objective             JSONB NOT NULL DEFAULT '{}'::jsonb,
    evaluation            JSONB NOT NULL DEFAULT '{}'::jsonb,
    decision              JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (run_id, step)
);

CREATE INDEX IF NOT EXISTS rolling_decisions_run_step
    ON sched.rolling_decisions (run_id, step);
