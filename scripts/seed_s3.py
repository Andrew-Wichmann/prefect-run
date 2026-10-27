"""Write a deterministic copy of the fake S3 object (the ingest flow now generates its own each run)."""

import random
import sys
from pathlib import Path

import pyarrow.parquet as pq

sys.path.insert(0, str(Path(__file__).parents[1] / "flows"))

from instruments import make_instruments  # noqa: E402

table = make_instruments(random.Random(0), 200)
out = Path(__file__).parents[1] / "flows" / "fake_s3" / "instruments.parquet"
pq.write_table(table, out)
print(f"wrote {table.num_rows} rows to {out}")
