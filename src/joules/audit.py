import os
from datetime import datetime, timezone

import psycopg
import pyarrow as pa
from prefect.runtime import flow_run


AUDIT_URL_ENV = "AUDIT_DATABASE_URL"

_INSERT = """
INSERT INTO stage_audit (
    flow_name, flow_run_id, flow_run_name, task_run_id, task_run_name,
    stage_name, key_column, item_key, status, detail
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def record(stage_name: str, key_column: str, statuses: pa.Table, task_run_id: str) -> None:
    """Append one audit row per row of the status table (``primary_key``, ``status``, ``detail``). No-op if ``AUDIT_DATABASE_URL`` is unset."""
    url = os.environ.get(AUDIT_URL_ENV)
    if not url or not statuses.num_rows:
        return
    meta = (flow_run.flow_name, flow_run.id, flow_run.name, task_run_id, stage_name, stage_name, key_column)
    cols = [statuses[c].to_pylist() for c in (key_column, "status", "detail")]
    rows = [(*meta, str(k), s, d) for k, s, d in zip(*cols)]
    with psycopg.connect(url) as conn:
        conn.cursor().executemany(_INSERT, rows)


def record_evicted(evicted: list[dict], flow_run_id: str | None = None) -> None:
    """Append one ``evicted`` row per deleted cache entry, so the audit log shows when a job's stage results were dropped."""
    url = os.environ.get(AUDIT_URL_ENV)
    if not url or not evicted:
        return
    rows = [
        (e["job"], flow_run_id, None, None, None, e["stage"], "cache_key", e["cache_key"], "evicted",
         f"expired at {datetime.fromtimestamp(e['expires_at'], timezone.utc).isoformat()}")
        for e in evicted
    ]
    with psycopg.connect(url) as conn:
        conn.cursor().executemany(_INSERT, rows)

