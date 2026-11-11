import pyarrow as pa

from joules import stage
from stages import init
from stages.stub import mock_work, with_failures

IN = init.OUT
OUT = IN

MOCK_FAILURE_REASONS = [
    "price is null",
    "price differs from previous close by more than 20%",
    "quote is stale (older than 15 minutes)",
    "bid is above ask",
    "instrument_type is not recognised",
]
"""Why the stub fails a row; a real check would report what it actually found."""


@stage(in_schema=IN, out_schema=OUT)
def dq(table: pa.Table):
    """Data quality checks on the raw quotes; failing rows are dropped from the output."""
    mock_work()
    return with_failures(table, "passed", MOCK_FAILURE_REASONS)
