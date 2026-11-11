"""Stage results (the data table and its status table) stored as one plain Parquet file.

The file is the data table; the status table (``primary_key``, ``status``, ``detail`` for every input
row, including the ones the stage dropped) rides in the file's key-value metadata under
``joules.statuses`` as base64 Parquet, so any Parquet reader opens it. Prefect keeps its own bookkeeping in a separate
metadata file (see ``cache.policy_for``'s ``key_storage``), so the result file is raw bytes.
"""

import base64
import io

import pyarrow as pa
import pyarrow.parquet as pq
from prefect.serializers import Serializer
from pydantic import Field


def _parquet(table: pa.Table) -> bytes:
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="zstd")
    return sink.getvalue()


STATUSES_KEY = b"joules.statuses"


class ParquetSerializer(Serializer):
    type: str = Field(default="joules-parquet", frozen=True)

    def dumps(self, obj: tuple[pa.Table, pa.Table]) -> bytes:  # type: ignore[override]
        table, statuses = obj
        meta = {**(table.schema.metadata or {}), STATUSES_KEY: base64.b64encode(_parquet(statuses))}
        return _parquet(table.replace_schema_metadata(meta))

    def loads(self, blob: bytes) -> tuple[pa.Table, pa.Table]:  # type: ignore[override]
        table = pq.read_table(io.BytesIO(blob))
        meta = dict(table.schema.metadata or {})
        statuses = pq.read_table(io.BytesIO(base64.b64decode(meta.pop(STATUSES_KEY))))
        return table.replace_schema_metadata(meta or None), statuses
