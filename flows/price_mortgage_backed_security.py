from joule import job
from stages.calibration import calibration
from stages.common import DELIVERY_SLA, DURATION_SLA_S, read_raw
from stages.dq import dq
from stages.init import init
from stages.price_mortgage_backed_security import price_mortgage_backed_security as price_mbs
from stages.upload import upload


@job(
    name="price-mortgage-backed-security",
    stages=[init, dq, calibration, price_mbs, upload],
    sla=DELIVERY_SLA,
    duration_sla=DURATION_SLA_S,
)
def price_mortgage_backed_security(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = price_mbs(table)
    table = upload(table)
    return table.num_rows
