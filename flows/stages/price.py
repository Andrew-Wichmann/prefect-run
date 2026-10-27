import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import CALIBRATED, PRICED, mock_work, with_failures


REASONS = ["price is not finite", "no market data to price against"]


@stage(in_schema=CALIBRATED, out_schema=PRICED)
def price(table: pa.Table):
    """Price each contract off the calibrated curve."""
    mock_work()
    priced = pc.multiply(table["last"], pc.add(1.0, table["curve_shift"]))
    table = table.append_column("price", priced)
    return with_failures(table, Status.PRICED, REASONS)
