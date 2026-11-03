import os

from joule import Link, job, link
from prefect.runtime import flow_run
from stages.calibration import calibration
from stages.common import DELIVERY_SLA, DURATION_SLA_S, RETENTION, read_raw
from stages.dq import dq
from stages.init import init
from stages.stress_mortgage_backed_security import stress_mortgage_backed_security as stress_mbs
from stages.upload import upload


@job(
    retention=RETENTION,
    name="stress-mortgage-backed-security",
    stages=[init, dq, calibration, stress_mbs, upload],
    sla=DELIVERY_SLA,
    duration_sla=DURATION_SLA_S,
    links=[Link("Margin dashboard (example)", "https://grafana.example.com/d/margin?var-cob={cob}")],
)
def stress_mortgage_backed_security(path: str):
    # attached while the run executes; a real job would build this from its trace id
    link("Prefect run", f"{os.environ.get('PREFECT_UI_URL', 'http://localhost:8080/prefect')}/runs/flow-run/{flow_run.id}")
    table = read_raw(path)
    table = init(table)
    table = dq(table)
    table = calibration(table)
    table = stress_mbs(table)
    table = upload(table)
    return table.num_rows
