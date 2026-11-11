from typing import Any, cast

from prefect import Flow, flow

JOBS = [
    "ingest_instruments",
    "stress_bond_futures",
    "stress_fixed_income_repos",
    "stress_interest_rate_swaps",
    "stress_mortgage_backed_security",
    "stress_to_be_announced",
]

MAINTENANCE = ["cleanup_cache"]  # not jobs: no stages, SLAs or dashboard page

if __name__ == "__main__":
    for name in [*JOBS, *MAINTENANCE]:
        # Prefect types from_source as a coroutine, but it runs synchronously here.
        loaded = cast(
            Flow[..., Any],
            flow.from_source(source="/opt/flows", entrypoint=f"{name}.py:{name}"),
        )
        loaded.deploy(
            name=name.replace("_", "-"),
            work_pool_name="local-pool",
            **({"cron": "0 3 * * *"} if name in MAINTENANCE else {}),  # daily, 03:00 UTC
        )
