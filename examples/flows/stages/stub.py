import os
import random
import time
from collections.abc import Sequence

import pyarrow as pa
import pyarrow.compute as pc

from joules import PRIMARY_KEY


FAIL_RATE = 0.015
"""Fraction of rows each stub stage randomly fails, to give runs some bad data."""


def with_failures(
    table: pa.Table, ok: str, reasons: Sequence[str], rate: float = FAIL_RATE
) -> tuple[pa.Table, pa.Table]:
    """Stub result: every row gets status ``ok`` except a random few, which are ``failed`` with a reason and dropped."""
    failed = pa.array([random.random() < rate for _ in range(table.num_rows)])
    detail = pa.array([random.choice(reasons) if f else None for f in failed.to_pylist()], pa.string())
    statuses = pa.table({PRIMARY_KEY: table[PRIMARY_KEY], "status": pc.if_else(failed, "failed", ok), "detail": detail})
    return table.filter(pc.invert(failed)), statuses


def mock_work(low: float = 1.0, high: float = 5.0) -> None:
    """Pretend to process for a while so runs take a realistic, varying time.

    ``JOULES_MOCK_SCALE`` multiplies the time, to stage a deliberately slow run."""
    time.sleep(random.uniform(low, high) * float(os.environ.get("JOULES_MOCK_SCALE", "1")))
