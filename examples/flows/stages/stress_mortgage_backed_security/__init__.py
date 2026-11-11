import pyarrow as pa
import pyarrow.compute as pc

from joule import stage
from stages import stress
from stages.stress.scenarios import add_scenarios
from stages.stub import mock_work, with_failures

IN = stress.IN
OUT = stress.OUT

PREPAYMENT_HAIRCUT = 0.99


REASONS = ["prepayment model failed", "pool factor missing"]


@stage(in_schema=IN, out_schema=OUT)
def stress_mortgage_backed_security(table: pa.Table):
    """Stress pass-through MBS off the calibrated curve, less a prepayment haircut (stub)."""
    mock_work()
    curve_price = pc.multiply(table["price"], pc.add(1.0, table["curve_shift"]))
    table = add_scenarios(table, pc.multiply(curve_price, PREPAYMENT_HAIRCUT))
    return with_failures(table, "stressed", REASONS)
