from joule import job
from stages.calibration import calibration
from stages.common import DELIVERY_SLA, DURATION_SLA_S, RETENTION, read_raw
from stages.dq import dq
from stages.init import init
from stages.price import price
from stages.upload import upload


@job(
    retention=RETENTION,
    name="price-fixed-income-repos",
    stages=[init, dq, calibration, price, upload],
    sla=DELIVERY_SLA,
    duration_sla=DURATION_SLA_S,
)
def price_fixed_income_repos(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = price(table)
    table = upload(table)
    return table.num_rows
