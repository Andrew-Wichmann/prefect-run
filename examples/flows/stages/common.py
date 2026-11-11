import os
import random
import time
from collections.abc import Sequence
from datetime import timedelta

import pyarrow as pa
import pyarrow.compute as pc

from joule import PRIMARY_KEY, Detail

SCENARIOS = 700
SCENARIO_FIELDS = [pa.field(f"pricing_scenario_{i}", pa.float64()) for i in range(1, SCENARIOS + 1)]
_SHOCKS = (lambda r: [r.gauss(0.0, 0.08) for _ in range(SCENARIOS)])(random.Random(2026))  # one market move per scenario, the same in every job


RETENTION = timedelta(days=30)  # how long the pricing jobs keep their stage results

FAIL_RATE = 0.015
"""Fraction of rows each stub stage randomly fails, to give runs some bad data."""


def with_failures(
    table: pa.Table, ok: str, reasons: Sequence[str], rate: float = FAIL_RATE
) -> tuple[pa.Table, dict[object, Detail]]:
    """Stub outcome: every row gets ``ok`` except a random few, which fail with a reason and are dropped."""
    keys = table[PRIMARY_KEY].to_pylist()
    failed = {k: random.choice(reasons) for k in keys if random.random() < rate}
    statuses: dict[object, Detail] = {k: ("failed", failed[k]) if k in failed else ok for k in keys}
    is_failed = pc.is_in(table[PRIMARY_KEY], value_set=pa.array(sorted(failed), pa.string()))
    return table.filter(pc.invert(is_failed)), statuses


def add_scenarios(table: pa.Table, base: pa.ChunkedArray | pa.Array) -> pa.Table:
    """Append the 700 ``pricing_scenario_N`` columns: ``base`` repriced under each scenario's market move,
    scaled by a per-instrument sensitivity (stub for the real revaluation)."""
    beta = pa.array([random.uniform(0.4, 1.6) for _ in range(len(base))])
    prices = [pc.round(pc.multiply(base, pc.add(1.0, pc.multiply(beta, shock))), 4) for shock in _SHOCKS]
    columns = [*table.columns, *prices]
    return pa.Table.from_arrays(columns, schema=pa.schema([*table.schema, *SCENARIO_FIELDS]))


def mock_work(low: float = 1.0, high: float = 5.0) -> None:
    """Pretend to process for a while so runs take a realistic, varying time.

    ``JOULE_MOCK_SCALE`` multiplies the time, to stage a deliberately slow run."""
    time.sleep(random.uniform(low, high) * float(os.environ.get("JOULE_MOCK_SCALE", "1")))
