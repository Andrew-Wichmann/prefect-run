import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import PRICED, RAW, mock_work, with_failures


REASONS = ["no discount curve for swap currency", "swap fixing missing"]


@stage(in_schema=RAW, out_schema=PRICED)
def price_interest_rate_swaps(table: pa.Table):
    """Price swaps off their quoted fixed rate (stub).

    Swaps skip calibration, so this stage prices against a flat curve and fills
    ``curve_shift`` with 0.0 to produce the common PRICED schema.
    """
    table = table.append_column("curve_shift", pa.array([0.0] * table.num_rows))
    table = table.append_column("price", pc.subtract(100.0, table["last"]))
    return with_failures(table, Status.PRICED, REASONS)
