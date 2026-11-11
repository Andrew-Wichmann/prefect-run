import pyarrow as pa
import pyarrow.compute as pc

from joule import stage
from stages import dq, stress
from stages.stress.scenarios import add_scenarios
from stages.stub import with_failures

IN = dq.OUT  # swaps skip calibration
OUT = stress.OUT  # but still produce the shape upload takes

REASONS = ["no discount curve for swap currency", "swap fixing missing"]


@stage(in_schema=IN, out_schema=OUT)
def stress_interest_rate_swaps(table: pa.Table):
    """Stress swaps off their quoted fixed rate (stub).

    Swaps skip calibration, so this stage stresses against a flat curve and fills
    ``curve_shift`` with 0.0 to match the calibrated shape.
    """
    table = table.append_column("curve_shift", pa.array([0.0] * table.num_rows))
    table = add_scenarios(table, pc.subtract(100.0, table["price"]))
    return with_failures(table, "stressed", REASONS)
