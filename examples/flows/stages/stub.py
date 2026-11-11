import os
import random
import time
from collections.abc import Sequence

import pyarrow as pa
import pyarrow.compute as pc

from joules import PRIMARY_KEY, Detail


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


def mock_work(low: float = 1.0, high: float = 5.0) -> None:
    """Pretend to process for a while so runs take a realistic, varying time.

    ``JOULES_MOCK_SCALE`` multiplies the time, to stage a deliberately slow run."""
    time.sleep(random.uniform(low, high) * float(os.environ.get("JOULES_MOCK_SCALE", "1")))
