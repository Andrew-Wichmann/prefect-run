import asyncio
import os
import random
from pathlib import Path

import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq
from prefect import get_run_logger
from prefect.deployments import run_deployment
from prefect.runtime import flow_run

from instruments import JOB_FOR, InstrumentType, make_instruments
from joule import job

DATA_DIR = Path(os.environ.get("JOULE_DATA_DIR", "/opt/data"))


def download(key: str, dest: Path) -> Path:
    """Stand-in for an S3 GetObject: each call "downloads" a different random instrument file."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    rng = random.Random()
    pq.write_table(make_instruments(rng, rng.randint(124, 324)), dest)
    return dest


@job(name="ingest-instruments")
async def ingest_instruments(key: str = "instruments.parquet"):
    log = get_run_logger()
    run_dir = DATA_DIR / (flow_run.id or "local")

    downloaded = download(key, run_dir / "downloaded.parquet")
    table = pq.read_table(downloaded)
    log.info(f"downloaded s3://fake/{key}: {table.num_rows} rows")

    pending = []
    for itype in InstrumentType:
        part = table.filter(pc.equal(table["instrument_type"], pa.scalar(itype.value)))
        if part.num_rows == 0:
            continue
        path = run_dir / f"{itype.value}.parquet"
        pq.write_table(part, path)

        deployment = JOB_FOR.get(itype)
        if deployment is None:
            log.info(f"{itype.value}: {part.num_rows} rows written, no job for this type")
            continue
        log.info(f"{itype.value}: {part.num_rows} rows -> {deployment}")
        pending.append(run_deployment(name=deployment, parameters={"path": str(path)}))

    # Each one is a subflow of this run; all are started together and awaited together.
    children = await asyncio.gather(*pending)
    log.info(f"{len(children)} subflow runs finished: {[c.state_name for c in children]}")
    return table.num_rows
