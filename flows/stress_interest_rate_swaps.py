from joule import job
from stages.common import DELIVERY_SLA, DURATION_SLA_S, RETENTION, read_raw
from stages.dq import dq
from stages.init import init
from stages.stress_interest_rate_swaps import stress_interest_rate_swaps as stress_swaps
from stages.upload import upload


@job(
    retention=RETENTION,
    name="stress-interest-rate-swaps",
    stages=[init, dq, stress_swaps, upload],
    sla=DELIVERY_SLA,
    duration_sla=DURATION_SLA_S,
)
def stress_interest_rate_swaps(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = stress_swaps(table)
    table = upload(table)
    return table.num_rows
