from joule import job
from stages.common import DELIVERY_SLA, DURATION_SLA_S, RETENTION, read_raw
from stages.dq import dq
from stages.init import init
from stages.price_interest_rate_swaps import price_interest_rate_swaps as price_swaps
from stages.upload import upload


@job(
    retention=RETENTION,
    name="price-interest-rate-swaps",
    stages=[init, dq, price_swaps, upload],
    sla=DELIVERY_SLA,
    duration_sla=DURATION_SLA_S,
)
def price_interest_rate_swaps(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = price_swaps(table)
    table = upload(table)
    return table.num_rows
