import pyarrow as pa
import pyarrow.compute as pc

from joule import Status, stage
from stages.common import CALIBRATED, PRICED, mock_work, with_failures

PREPAYMENT_HAIRCUT = 0.99


REASONS = ["prepayment model failed", "pool factor missing"]


@stage(in_schema=CALIBRATED, out_schema=PRICED)
def price_mortgage_backed_security(table: pa.Table):
    """Price pass-through MBS off the calibrated curve, less a prepayment haircut (stub)."""
    mock_work()
    curve_price = pc.multiply(table["last"], pc.add(1.0, table["curve_shift"]))
    table = table.append_column("price", pc.multiply(curve_price, PREPAYMENT_HAIRCUT))
    return with_failures(table, Status.PRICED, REASONS)
