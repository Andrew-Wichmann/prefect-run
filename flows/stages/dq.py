import pyarrow as pa

from joule import Status, stage
from stages.common import RAW, mock_work, with_failures

REASONS = [
    "last price is null",
    "last price differs from previous close by more than 20%",
    "quote is stale (older than 15 minutes)",
    "bid is above ask",
    "instrument_type is not recognised",
]
"""Why the stub fails a row; a real check would report what it actually found."""


@stage(in_schema=RAW, out_schema=RAW)
def dq(table: pa.Table):
    """Data quality checks on the raw quotes; failing rows are dropped from the output."""
    mock_work()
    return with_failures(table, Status.PASSED, REASONS)
