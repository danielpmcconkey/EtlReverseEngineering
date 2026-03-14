-- Reverse-engineering workflow engine: task queue and job state tables.
-- All tables live in the existing `control` schema with `re_` prefix.

CREATE TABLE IF NOT EXISTS control.re_task_queue (
    id          bigserial       PRIMARY KEY,
    job_id      text            NOT NULL,
    node_name   text            NOT NULL,
    status      text            NOT NULL DEFAULT 'pending',
    created_at  timestamptz     NOT NULL DEFAULT now(),
    claimed_at  timestamptz,
    completed_at timestamptz
);

-- FIFO claiming: pending tasks ordered by creation time.
CREATE INDEX IF NOT EXISTS ix_re_task_queue_fifo
    ON control.re_task_queue (created_at)
    WHERE status = 'pending';

-- At most one active (pending or claimed) task per job.
CREATE UNIQUE INDEX IF NOT EXISTS ix_re_task_queue_one_active
    ON control.re_task_queue (job_id)
    WHERE status IN ('pending', 'claimed');

CREATE TABLE IF NOT EXISTS control.re_engine_config (
    id          integer         PRIMARY KEY DEFAULT 1 CHECK (id = 1),
    clutch_engaged boolean      NOT NULL DEFAULT false,
    updated_at  timestamptz     NOT NULL DEFAULT now()
);

-- Seed the single config row if it doesn't exist.
INSERT INTO control.re_engine_config (id) VALUES (1) ON CONFLICT DO NOTHING;

CREATE TABLE IF NOT EXISTS control.re_job_state (
    job_id              text        PRIMARY KEY,
    current_node        text        NOT NULL DEFAULT 'LocateOgSourceFiles',
    status              text        NOT NULL DEFAULT 'RUNNING',
    main_retry_count    integer     NOT NULL DEFAULT 0,
    conditional_counts  jsonb       NOT NULL DEFAULT '{}',
    last_rejection_reason text,
    fbr_return_pending  boolean     NOT NULL DEFAULT false,
    triage_results      jsonb       NOT NULL DEFAULT '{}',
    triage_rewind_target text,
    updated_at          timestamptz NOT NULL DEFAULT now()
);
