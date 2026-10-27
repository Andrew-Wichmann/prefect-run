"""Stage results (the output table and its per-row outcomes) stored as one plain Parquet file.

The file is the output table; the per-row outcomes (``key``, ``status``, ``detail`` for every input
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

from joule.status import Outcome, Status, split_outcome


def _parquet(table: pa.Table) -> bytes:
    sink = io.BytesIO()
    pq.write_table(table, sink, compression="zstd")
    return sink.getvalue()


OUTCOMES_KEY = b"joule.outcomes"


class ParquetSerializer(Serializer):
    type: str = Field(default="joule-parquet", frozen=True)

    def dumps(self, obj: tuple[pa.Table, Mapping[object, Outcome]]) -> bytes:  # type: ignore[override]
        table, outcomes = obj
        split = [split_outcome(v) for v in outcomes.values()]
        payload = json.dumps(
            {"key": list(outcomes), "status": [s for s, _ in split], "detail": [d for _, d in split]}
        )
        table = table.replace_schema_metadata({**(table.schema.metadata or {}), OUTCOMES_KEY: payload.encode()})
        return _parquet(table)

    def loads(self, blob: bytes) -> tuple[pa.Table, dict[object, Outcome]]:  # type: ignore[override]
        table = pq.read_table(io.BytesIO(blob))
        meta = dict(table.schema.metadata or {})
        o = json.loads(meta.pop(OUTCOMES_KEY))
        outcomes: dict[object, Outcome] = {
            k: (Status(s), d) if d is not None else Status(s) for k, s, d in zip(o["key"], o["status"], o["detail"])
        }
        return table.replace_schema_metadata(meta or None), outcomes
