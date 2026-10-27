import os
from collections.abc import Mapping

import psycopg
from prefect.runtime import flow_run

from joule.status import Outcome, split_outcome

AUDIT_URL_ENV = "AUDIT_DATABASE_URL"

_INSERT = """
INSERT INTO stage_audit (
    flow_name, flow_run_id, flow_run_name, task_run_id, task_run_name,
    stage_name, key_column, item_key, status, detail
) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


def record(stage_name: str, key_column: str, statuses: Mapping[object, Outcome], task_run_id: str) -> None:
    """Append one audit row per item (status, plus the detail if the outcome has one). No-op if ``AUDIT_DATABASE_URL`` is unset."""
    url = os.environ.get(AUDIT_URL_ENV)
    if not url or not statuses:
        return
    meta = (flow_run.flow_name, flow_run.id, flow_run.name, task_run_id, stage_name, stage_name, key_column)
    rows = [(*meta, str(k), *split_outcome(v)) for k, v in statuses.items()]
    with psycopg.connect(url) as conn:
        conn.cursor().executemany(_INSERT, rows)
