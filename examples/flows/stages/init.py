import pyarrow as pa

from joule import Status, stage
from stages.common import RAW, mock_work, with_failures


REASONS = ["duplicate instrument in source file", "row could not be parsed"]


@stage(in_schema=RAW, out_schema=RAW)
def init(table: pa.Table):
    """Register every row loaded for the job."""
    mock_work()
    return with_failures(table, Status.INIT, REASONS)
