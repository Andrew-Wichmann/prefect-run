"""Stage results (the output table and its per-row details) stored as one plain Parquet file.

The file is the output table; the per-row details (``key``, ``status``, ``detail`` for every input
row, including the ones the stage dropped) ride in the file's key-value metadata under
``joule.outcomes``, so any Parquet reader opens it. Prefect keeps its own bookkeeping in a separate
metadata file (see ``cache.policy_for``'s ``key_storage``), so the result file is raw bytes.
"""

import io
import json
from collections.abc import Mapping

import pyarrow as pa
import pyarrow.parquet as pq
from prefect.serializers import Serializer
from pydantic import Field

from joule.status import Detail, split_detail


def _parquet(table: pa.Table) -> bytes:
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="zstd")
    return sink.getvalue()


DETAILS_KEY = b"joule.outcomes"  # name kept so cached results from before the rename still load


class ParquetSerializer(Serializer):
    type: str = Field(default="joule-parquet", frozen=True)

    def dumps(self, obj: tuple[pa.Table, Mapping[object, Detail]]) -> bytes:  # type: ignore[override]
        table, details = obj
        split = [split_detail(v) for v in details.values()]
        payload = json.dumps(
            {"key": list(details), "status": [s for s, _ in split], "detail": [d for _, d in split]}
        )
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), DETAILS_KEY: payload.encode()})
        return _parquet(table)

    def loads(self, blob: bytes) -> tuple[pa.Table, dict[object, Detail]]:  # type: ignore[override]
        table = pq.read_table(io.BytesIO(blob))
        meta = dict(table.schema.metadata or {})
        o = json.loads(meta.pop(DETAILS_KEY))
        details: dict[object, Detail] = {
            k: (s, d) if d is not None else s for k, s, d in zip(o["key"], o["status"], o["detail"])
        }
        return table.replace_schema_metadata(meta or None), details
