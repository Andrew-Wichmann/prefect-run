import pyarrow as pa
import pyarrow.compute as pc

from joule import stage
from stages import calibration
from stages.common import SCENARIO_FIELDS, add_scenarios, mock_work, with_failures

IN = calibration.OUT
OUT = pa.schema([*IN, *SCENARIO_FIELDS])  # every stress stage produces this shape, which is what upload takes

REASONS = ["stressed price is not finite", "no market data to stress against"]


@stage(in_schema=IN, out_schema=OUT)
def stress(table: pa.Table):
    """Stress each contract off the calibrated curve."""
    mock_work()
    table = add_scenarios(table, pc.multiply(table["price"], pc.add(1.0, table["curve_shift"])))
    return with_failures(table, "stressed", REASONS)
