import pyarrow as pa

from joule import Status, stage
from stages.common import STRESSED, mock_work, with_failures


REASONS = ["downstream rejected the record", "upload timed out"]


@stage(in_schema=STRESSED, out_schema=STRESSED)
def upload(table: pa.Table):
    """Publish stressed prices downstream (stub: nothing is sent anywhere yet)."""
    mock_work()
    return with_failures(table, Status.UPLOADED, REASONS)
