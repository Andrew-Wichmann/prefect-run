import pyarrow as pa
import pyarrow.parquet as pq

from joules import PRIMARY_KEY, stage
from stages.stub import mock_work, with_failures

IN = pa.schema([(PRIMARY_KEY, pa.string()), ("price", pa.float64())])
OUT = IN

MOCK_FAILURE_REASONS = ["duplicate instrument in source file", "row could not be parsed"]


def read_raw(path: str) -> pa.Table:
    """Load a job's input parquet, keeping just the columns this stage takes."""
    return pq.read_table(path, columns=IN.names)


@stage(in_schema=IN, out_schema=OUT)
def init(table: pa.Table):
    """Register every row loaded for the job."""
    mock_work()
    return with_failures(table, "init", MOCK_FAILURE_REASONS)
