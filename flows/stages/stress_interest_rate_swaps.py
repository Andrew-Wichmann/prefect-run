import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import STRESSED, RAW, add_scenarios, mock_work, with_failures


REASONS = ["no discount curve for swap currency", "swap fixing missing"]


@stage(in_schema=RAW, out_schema=STRESSED)
def stress_interest_rate_swaps(table: pa.Table):
    """Stress swaps off their quoted fixed rate (stub).

    Swaps skip calibration, so this stage stresses against a flat curve and fills
    ``curve_shift`` with 0.0 to produce the common STRESSED schema.
    """
    table = table.append_column("curve_shift", pa.array([0.0] * table.num_rows))
    table = add_scenarios(table, pc.subtract(100.0, table["price"]))
    return with_failures(table, Status.STRESSED, REASONS)
