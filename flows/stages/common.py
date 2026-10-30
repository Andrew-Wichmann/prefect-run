import os
import random
import time
from collections.abc import Sequence
from datetime import timedelta

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from joule import PRIMARY_KEY, Outcome, Sla, Status

# Schemas chain: each stage's out_schema is the next stage's in_schema.
RAW = pa.schema([(PRIMARY_KEY, pa.string()), ("price", pa.float64())])
CALIBRATED = RAW.append(pa.field("curve_shift", pa.float64()))
SCENARIOS = 700
SCENARIO_COLUMNS = [f"pricing_scenario_{i}" for i in range(1, SCENARIOS + 1)]
STRESSED = pa.schema([*CALIBRATED, *(pa.field(name, pa.float64()) for name in SCENARIO_COLUMNS)])
_SHOCKS = (lambda r: [r.gauss(0.0, 0.08) for _ in range(SCENARIOS)])(random.Random(2026))  # one market move per scenario, the same in every job


DELIVERY_SLA = Sla(time="07:00", tz="America/New_York", day_offset=1)
"""Pricing lands by 07:00 New York time the morning after the close-of-business date (T+1)."""
DURATION_SLA_S = 30
RETENTION = timedelta(days=30)  # how long the pricing jobs keep their stage results
"""Seconds a pricing run may take."""

FAIL_RATE = 0.015
"""Fraction of rows each stub stage randomly fails, to give runs some bad data."""


def with_failures(
    table: pa.Table, ok: Status, reasons: Sequence[str], rate: float = FAIL_RATE
) -> tuple[pa.Table, dict[object, Outcome]]:
    """Stub outcome: every row gets ``ok`` except a random few, which fail with a reason and are dropped."""
    keys = table[PRIMARY_KEY].to_pylist()
    failed = {k: random.choice(reasons) for k in keys if random.random() < rate}
    statuses: dict[object, Outcome] = {k: (Status.FAILED, failed[k]) if k in failed else ok for k in keys}
    is_failed = pc.is_in(table[PRIMARY_KEY], value_set=pa.array(sorted(failed), pa.string()))
    return table.filter(pc.invert(is_failed)), statuses


def add_scenarios(table: pa.Table, base: pa.ChunkedArray | pa.Array) -> pa.Table:
    """Append the 700 ``pricing_scenario_N`` columns: ``base`` repriced under each scenario's market move,
    scaled by a per-instrument sensitivity (stub for the real revaluation)."""
    beta = pa.array([random.uniform(0.4, 1.6) for _ in range(len(base))])
    prices = [pc.round(pc.multiply(base, pc.add(1.0, pc.multiply(beta, shock))), 4) for shock in _SHOCKS]
    columns = [*table.columns, *prices]
    return pa.Table.from_arrays(columns, schema=pa.schema([*table.schema, *(pa.field(n, pa.float64()) for n in SCENARIO_COLUMNS)]))


def read_raw(path: str) -> pa.Table:
    """Load a job's input parquet, keeping just the RAW columns."""
    return pq.read_table(path, columns=[PRIMARY_KEY, "price"])


def mock_work(low: float = 1.0, high: float = 5.0) -> None:
    """Pretend to process for a while so runs take a realistic, varying time.

    ``JOULE_MOCK_SCALE`` multiplies the time, to stage a deliberately slow run."""
    time.sleep(random.uniform(low, high) * float(os.environ.get("JOULE_MOCK_SCALE", "1")))
