import pyarrow as pa

from joules import stage
from stages import stress
from stages.stub import mock_work, with_failures

IN = stress.OUT
OUT = IN


MOCK_FAILURE_REASONS = ["downstream rejected the record", "upload timed out"]


@stage(in_schema=IN, out_schema=OUT)
def upload(table: pa.Table):
    """Publish stressed prices downstream (stub: nothing is sent anywhere yet)."""
    mock_work()
    return with_failures(table, "uploaded", MOCK_FAILURE_REASONS)
