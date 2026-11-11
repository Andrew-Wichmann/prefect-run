import pyarrow as pa

from joules import stage
from stages import dq
from stages.stub import mock_work, with_failures

IN = dq.OUT
OUT = IN.append(pa.field("curve_shift", pa.float64()))

MOCK_FAILURE_REASONS = ["curve failed to converge", "no curve available for instrument", "calibration residual above tolerance"]


@stage(in_schema=IN, out_schema=OUT)
def calibration(table: pa.Table):
    """Calibrate the curve; attaches a per-contract curve shift."""
    mock_work()
    table = table.append_column("curve_shift", pa.array([0.0] * table.num_rows))
    return with_failures(table, "calibrated", MOCK_FAILURE_REASONS)
