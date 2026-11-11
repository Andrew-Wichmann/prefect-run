import functools
import inspect
from collections.abc import Callable
from typing import Any, Concatenate, ParamSpec, cast

import pyarrow as pa
import pyarrow.compute as pc
from prefect import Task

from joules import audit, cache, trace
from joules.job import JOBS
from joules.serializer import ParquetSerializer


PRIMARY_KEY = "primary_key"
"""Every table in joules is keyed by this column; it is not configurable."""

STATUS = "status"
DETAIL = "detail"
"""The status table's columns: ``primary_key``, ``status`` (any non-empty string) and optionally ``detail`` (a note)."""

P = ParamSpec("P")

StageResult = tuple[pa.Table, pa.Table]


class StageContractError(TypeError):
    """A stage broke the ``Table -> (Table, {key: status})`` contract."""


def _check_schema(name: str, label: str, expected: pa.Schema, table: pa.Table) -> None:
    if not table.schema.equals(expected, check_metadata=False):
        raise StageContractError(
            f"stage {name!r} {label} schema does not match.\n"
            f"expected:\n{expected}\ngot:\n{table.schema}"
        )


def _input_keys(name: str, in_schema: pa.Schema, table: object) -> list:
    if not isinstance(table, pa.Table):
        raise StageContractError(
            f"stage {name!r} must receive a pyarrow.Table, got {type(table).__name__}"
        )
    _check_schema(name, "input", in_schema, table)
    if PRIMARY_KEY not in table.column_names:
        raise StageContractError(
            f"stage {name!r} input has no primary key column {PRIMARY_KEY!r}"
        )
    keys = table.column(PRIMARY_KEY).to_pylist()
    if len(set(keys)) != len(keys):
        raise StageContractError(
            f"stage {name!r} input has duplicate values in primary key {PRIMARY_KEY!r}"
        )
    return keys


def _check_output(
    name: str, out_schema: pa.Schema, input_keys: list, result: object
) -> StageResult:
    """Validate a stage's return value; the status table comes back with a ``detail`` column even if it had none."""
    if not (isinstance(result, tuple) and len(result) == 2):
        raise StageContractError(f"stage {name!r} must return (data table, status table)")
    table, statuses = result
    for what, t in (("data", table), ("status", statuses)):
        if not isinstance(t, pa.Table):
            raise StageContractError(f"stage {name!r} {what} result must be a pyarrow.Table, got {type(t).__name__}")
    _check_schema(name, "output", out_schema, table)
    cols = set(statuses.column_names)
    if not {PRIMARY_KEY, STATUS} <= cols <= {PRIMARY_KEY, STATUS, DETAIL}:
        raise StageContractError(
            f"stage {name!r} status table must have columns {PRIMARY_KEY!r}, {STATUS!r} and optionally {DETAIL!r}, "
            f"got {statuses.column_names}"
        )
    keys = statuses[PRIMARY_KEY].to_pylist()
    missing, extra = set(input_keys) - set(keys), set(keys) - set(input_keys)
    if missing or extra or len(keys) != len(set(keys)):
        raise StageContractError(
            f"stage {name!r} status table must have exactly one row per input {PRIMARY_KEY!r} value "
            f"(missing: {sorted(map(repr, missing))[:5]}, unknown: {sorted(map(repr, extra))[:5]}, "
            f"{len(keys)} rows for {len(input_keys)} inputs)"
        )
    text = (pa.string(), pa.large_string())
    status = statuses[STATUS]
    if status.type not in text or status.null_count or pc.any(pc.equal(status, "")).as_py():
        raise StageContractError(f"stage {name!r} {STATUS!r} must be a non-empty string for every row")
    detail = statuses[DETAIL] if DETAIL in cols else pa.nulls(statuses.num_rows, pa.string())
    if detail.type not in text and detail.type != pa.null():
        raise StageContractError(f"stage {name!r} {DETAIL!r} must be a string column")
    normal = pa.table({PRIMARY_KEY: statuses[PRIMARY_KEY], STATUS: status.cast(pa.string()), DETAIL: detail.cast(pa.string())})
    return table, normal


class _Stage(Task[Any, Any]):
    """A task whose result (data table + status table) is cached across runs.

    Calling it returns just the table. The statuses are written to the audit log on every
    call, cache hit or not, so each run's audit trail is complete."""

    def __call__(self, *args: Any, **kwargs: Any) -> pa.Table:  # type: ignore[override]
        trace.note(self.name)
        task = self.with_options(refresh_cache=True) if cache.is_busted(self.name) else self
        state = Task.__call__(task, *args, return_state=True, **kwargs)
        table, statuses = state.result()  # re-raises if the stage failed
        task_run_id = str(state.state_details.task_run_id)
        job = cache._job_name()
        if job in JOBS and isinstance(self.cache_policy, cache.StageInputs):
            storage_key = state.data.metadata.storage_key  # type: ignore[union-attr]
            bound = inspect.signature(self.fn).bind(*args, **kwargs)
            bound.apply_defaults()
            cache_key = self.cache_policy.compute_key(None, dict(bound.arguments), {})  # type: ignore[arg-type]
            cache.keep_until(cache_key, storage_key, job, self.name, JOBS[job].retention)
        audit.record(self.name, PRIMARY_KEY, statuses, task_run_id)
        return table


def stage(
    *,
    in_schema: pa.Schema,
    out_schema: pa.Schema,
    **task_kwargs: Any,
) -> Callable[
    [Callable[Concatenate[pa.Table, P], StageResult]],
    Task[Concatenate[pa.Table, P], pa.Table],
]:
    """Wrap a function as a Prefect task with an explicit table contract.

    ``in_schema`` and ``out_schema`` are mandatory: the table passed in must
    match ``in_schema`` and the table returned must match ``out_schema``
    (field names, order, types and nullability; schema metadata is ignored).

    The function takes a ``pyarrow.Table`` and returns two tables: the output data, and a status table with
    columns ``primary_key``, ``status`` (any non-empty string; a job names its own) and optionally ``detail``
    (a note recorded next to the status). Rows are identified by the ``PRIMARY_KEY`` column (fixed, not
    configurable), which must be in both schemas and unique in the input. The status table must have exactly one
    row per input row; rows may be filtered out of the data table.

    The wrapper consumes the status table (validates it and writes it to the audit log); callers of the stage
    only ever see the data table.

    Results are cached across runs on the stage's inputs and code (override with
    ``cache_policy=``) and stored as Parquet, not pickle (see ``joules.serializer``); see ``joules.cache`` for busting the cache from a stage.

    Usage: ``@stage(in_schema=IN, out_schema=OUT, retries=2)``.
    """
    for label, schema in (("in_schema", in_schema), ("out_schema", out_schema)):
        if PRIMARY_KEY not in schema.names:
            raise ValueError(f"{label} must have a {PRIMARY_KEY!r} field")

    def decorate(
        f: Callable[Concatenate[pa.Table, P], StageResult],
    ) -> Task[Concatenate[pa.Table, P], pa.Table]:
        @functools.wraps(f)
        def checked(table: pa.Table, *args: P.args, **kwargs: P.kwargs) -> StageResult:
            input_keys = _input_keys(f.__name__, in_schema, table)
            return _check_output(f.__name__, out_schema, input_keys, f(table, *args, **kwargs))

        task_kwargs.setdefault("task_run_name", f.__name__)  # exact stage name, so readers need not strip Prefect's suffix
        task_kwargs.setdefault("result_serializer", ParquetSerializer())
        task_kwargs.setdefault("cache_policy", cache.policy_for(f.__name__, f, in_schema, out_schema))
        return cast(Task[Concatenate[pa.Table, P], pa.Table], _Stage(checked, **task_kwargs))

    return decorate
