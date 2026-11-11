from joule import job
from stages.calibration import calibration
from config import RETENTION
from stages.dq import dq
from stages.init import init, read_raw
from stages.stress_mortgage_backed_security import stress_mortgage_backed_security as stress_mbs
from stages.upload import upload


@job(
    retention=RETENTION,
    name="stress-mortgage-backed-security",
    stages=[init, dq, calibration, stress_mbs, upload],
)
def stress_mortgage_backed_security(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = stress_mbs(table)
    table = upload(table)
    return table.num_rows
