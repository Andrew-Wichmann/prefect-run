import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import CALIBRATED, PRICED, mock_work, with_failures

DROP = 0.25


REASONS = ["no TBA coupon available", "settlement date outside TBA calendar"]


@stage(in_schema=CALIBRATED, out_schema=PRICED)
def price_to_be_announced(table: pa.Table):
    """Price TBAs (forward-settling MBS, pool not yet specified): curve price less the drop (stub)."""
    mock_work()
    curve_price = pc.multiply(table["last"], pc.add(1.0, table["curve_shift"]))
    table = table.append_column("price", pc.subtract(curve_price, DROP))
    return with_failures(table, Status.PRICED, REASONS)
