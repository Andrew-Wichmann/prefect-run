import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import CALIBRATED, STRESSED, add_scenarios, mock_work, with_failures


REASONS = ["stressed price is not finite", "no market data to stress against"]


@stage(in_schema=CALIBRATED, out_schema=STRESSED)
def stress(table: pa.Table):
    """Stress each contract off the calibrated curve."""
    mock_work()
    table = add_scenarios(table, pc.multiply(table["price"], pc.add(1.0, table["curve_shift"])))
    return with_failures(table, Status.STRESSED, REASONS)
