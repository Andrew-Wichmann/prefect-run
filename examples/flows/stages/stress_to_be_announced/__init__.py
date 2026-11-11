import pyarrow as pa
import pyarrow.compute as pc

from joules import stage
from stages import stress
from stages.stress.scenarios import add_scenarios
from stages.stub import mock_work, with_failures

IN = stress.IN
OUT = stress.OUT

DROP = 0.25


MOCK_FAILURE_REASONS = ["no TBA coupon available", "settlement date outside TBA calendar"]


@stage(in_schema=IN, out_schema=OUT)
def stress_to_be_announced(table: pa.Table):
    """Stress TBAs (forward-settling MBS, pool not yet specified): curve price less the drop (stub)."""
    mock_work()
    curve_price = pc.multiply(table["price"], pc.add(1.0, table["curve_shift"]))
    table = add_scenarios(table, pc.subtract(curve_price, DROP))
    return with_failures(table, "stressed", MOCK_FAILURE_REASONS)
