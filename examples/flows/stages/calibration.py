import pyarrow as pa

from joule import Status, stage
from stages.common import CALIBRATED, RAW, mock_work, with_failures


REASONS = ["curve failed to converge", "no curve available for instrument", "calibration residual above tolerance"]


@stage(in_schema=RAW, out_schema=CALIBRATED)
def calibration(table: pa.Table):
    """Calibrate the curve; attaches a per-contract curve shift."""
    mock_work()
    table = table.append_column("curve_shift", pa.array([0.0] * table.num_rows))
    return with_failures(table, Status.CALIBRATED, REASONS)
