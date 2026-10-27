from joule import job
from stages.calibration import calibration
from stages.common import DELIVERY_SLA, DURATION_SLA_S, read_raw
from stages.dq import dq
from stages.init import init
from stages.price_to_be_announced import price_to_be_announced as price_tba
from stages.upload import upload


@job(
    name="price-to-be-announced",
    stages=[init, dq, calibration, price_tba, upload],
    sla=DELIVERY_SLA,
    duration_sla=DURATION_SLA_S,
)
def price_to_be_announced(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = price_tba(table)
    table = upload(table)
    return table.num_rows
