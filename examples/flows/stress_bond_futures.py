from joule import job
from stages.calibration import calibration
from stages.common import RETENTION
from stages.dq import dq
from stages.init import init, read_raw
from stages.stress import stress
from stages.upload import upload


@job(
    retention=RETENTION,
    name="stress-bond-futures",
    stages=[init, dq, calibration, stress, upload],
)
def stress_bond_futures(path: str):
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = stress(table)
    table = upload(table)
    return table.num_rows
