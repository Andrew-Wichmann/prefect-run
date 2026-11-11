from joule import job
from stages.calibration import calibration
from stages.common import RETENTION, read_raw
from stages.dq import dq
from stages.init import init
from stages.stress import stress
from stages.upload import upload


@job(
    retention=RETENTION,
    name="stress-fixed-income-repos",
    stages=[init, dq, calibration, stress, upload],
)
def stress_fixed_income_repos(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = stress(table)
    table = upload(table)
    return table.num_rows
