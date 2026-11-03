-- Append-only audit log: one row per (stage execution, item).
CREATE TABLE stage_audit (
    id            bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recorded_at   timestamptz NOT NULL DEFAULT clock_timestamp(),

    -- flow / task run metadata (NULL when a stage runs outside Prefect)
    flow_name     text,
    flow_run_id   uuid,
    flow_run_name text,
    task_run_id   uuid,
    task_run_name text,

    stage_name    text NOT NULL,
    key_column    text NOT NULL,
    item_key      text NOT NULL,
    status        text NOT NULL,
    detail        text  -- optional explanation, e.g. why a data quality check failed
);

CREATE INDEX stage_audit_item_idx ON stage_audit (item_key, id);
CREATE INDEX stage_audit_flow_run_idx ON stage_audit (flow_run_id, id);

-- Reject any change to history.
CREATE FUNCTION stage_audit_immutable() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    RAISE EXCEPTION 'stage_audit is append-only (% not allowed)', TG_OP;
END;
$$;

CREATE TRIGGER stage_audit_no_change
    BEFORE UPDATE OR DELETE ON stage_audit
    FOR EACH ROW EXECUTE FUNCTION stage_audit_immutable();

CREATE TRIGGER stage_audit_no_truncate
    BEFORE TRUNCATE ON stage_audit
    FOR EACH STATEMENT EXECUTE FUNCTION stage_audit_immutable();

-- Wake the audit UI whenever new history is appended.
CREATE FUNCTION stage_audit_notify() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    PERFORM pg_notify('stage_audit', '');
    RETURN NULL;
END;
$$;

CREATE TRIGGER stage_audit_notify
    AFTER INSERT ON stage_audit
    FOR EACH STATEMENT EXECUTE FUNCTION stage_audit_notify();

-- Links a run attaches to its card while it runs (a trace, a request, a dashboard for this run's result). Append-only too.
CREATE TABLE run_links (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    flow_run_id uuid NOT NULL,
    label       text NOT NULL,
    url         text NOT NULL CHECK (url ~ '^https?://')
);
CREATE INDEX run_links_run_idx ON run_links (flow_run_id, id);
CREATE TRIGGER run_links_no_change BEFORE UPDATE OR DELETE ON run_links FOR EACH ROW EXECUTE FUNCTION stage_audit_immutable();
CREATE TRIGGER run_links_no_truncate BEFORE TRUNCATE ON run_links FOR EACH STATEMENT EXECUTE FUNCTION stage_audit_immutable();
CREATE TRIGGER run_links_notify AFTER INSERT ON run_links FOR EACH STATEMENT EXECUTE FUNCTION stage_audit_notify();
