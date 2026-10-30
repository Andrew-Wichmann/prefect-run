import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import CALIBRATED, STRESSED, mock_work, with_failures


REASONS = ["stressed price is not finite", "no market data to stress against"]


@stage(in_schema=CALIBRATED, out_schema=STRESSED)
def stress(table: pa.Table):
    """Stress each contract off the calibrated curve."""
    mock_work()
    stressed = pc.multiply(table["price"], pc.add(1.0, table["curve_shift"]))
    table = table.append_column("stressed_price", stressed)
    return with_failures(table, Status.STRESSED, REASONS)
