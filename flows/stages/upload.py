import pyarrow as pa

from joule import Status, stage
from stages.common import PRICED, mock_work, with_failures


REASONS = ["downstream rejected the record", "upload timed out"]


@stage(in_schema=PRICED, out_schema=PRICED)
def upload(table: pa.Table):
    """Publish prices downstream (stub: nothing is sent anywhere yet)."""
    mock_work()
    return with_failures(table, Status.UPLOADED, REASONS)
