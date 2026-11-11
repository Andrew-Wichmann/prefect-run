from joule import job
from stages.calibration import calibration
from stages.common import RETENTION
from stages.dq import dq
from stages.init import init, read_raw
from stages.stress_to_be_announced import stress_to_be_announced as stress_tba
from stages.upload import upload


@job(
    retention=RETENTION,
    name="stress-to-be-announced",
    stages=[init, dq, calibration, stress_tba, upload],
)
def stress_to_be_announced(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = stress_tba(table)
    table = upload(table)
    return table.num_rows
