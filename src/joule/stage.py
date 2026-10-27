import functools
import inspect
from collections.abc import Callable, Mapping
from typing import Any, Concatenate, ParamSpec, cast

import pyarrow as pa
from prefect import Task

from joule import audit, cache, trace
from joule.job import JOBS
from joule.serializer import ParquetSerializer
from joule.status import Outcome, Status


PRIMARY_KEY = "primary_key"
"""Every table in joule is keyed by this column; it is not configurable."""

P = ParamSpec("P")

StageResult = tuple[pa.Table, Mapping[object, Outcome]]


class StageContractError(TypeError):
    """A stage broke the ``Table -> (Table, {key: Status})`` contract."""


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
) -> None:
    if not (isinstance(result, tuple) and len(result) == 2):
        raise StageContractError(
            f"stage {name!r} must return (pyarrow.Table, dict[key, Status | (Status, detail)])"
        )
    table, statuses = result
    if not isinstance(table, pa.Table):
        raise StageContractError(
            f"stage {name!r} must return a pyarrow.Table first, got {type(table).__name__}"
        )
    _check_schema(name, "output", out_schema, table)
    if not isinstance(statuses, dict):
        raise StageContractError(
            f"stage {name!r} must return a dict second, got {type(statuses).__name__}"
        )
    missing = set(input_keys) - set(statuses)
    extra = set(statuses) - set(input_keys)
    if missing or extra:
        raise StageContractError(
            f"stage {name!r} statuses must map 1:1 to the input's {PRIMARY_KEY!r} values "
            f"(missing: {sorted(map(repr, missing))[:5]}, "
            f"unknown: {sorted(map(repr, extra))[:5]})"
        )
    for v in statuses.values():
        status, detail = v if isinstance(v, tuple) and len(v) == 2 else (v, None)
        if not isinstance(status, Status) or not (detail is None or isinstance(detail, str)):
            raise StageContractError(
                f"stage {name!r} statuses must be a Status or (Status, detail str), got {v!r}"
            )


class _Stage(Task[Any, Any]):
    """A task whose result (table + statuses) is cached across runs.

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

    The function takes a ``pyarrow.Table`` and returns
    ``(pyarrow.Table, {primary_key_value: Status})``. A value may instead be
    ``(Status, "why")``; the detail is recorded in the audit log next to the status. Rows are identified by the
    ``PRIMARY_KEY`` column (fixed, not configurable), which must be in both
    schemas and unique in the input. The returned dict must have exactly one
    ``Status`` per input row; rows may be filtered out of the returned table.

    The wrapper consumes the dict (validates it and writes it to the audit
    log); callers of the stage only ever see the resulting table.

    Results are cached across runs on the stage's inputs and code (override with
    ``cache_policy=``) and stored as Parquet, not pickle (see ``joule.serializer``); see ``joule.cache`` for busting the cache from a stage.

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
            result = f(table, *args, **kwargs)
            _check_output(f.__name__, out_schema, input_keys, result)
            return result

        task_kwargs.setdefault("task_run_name", f.__name__)  # exact stage name, so readers need not strip Prefect's suffix
        task_kwargs.setdefault("result_serializer", ParquetSerializer())
        task_kwargs.setdefault("cache_policy", cache.policy_for(f.__name__, f, in_schema, out_schema))
        return cast(Task[Concatenate[pa.Table, P], pa.Table], _Stage(checked, **task_kwargs))

    return decorate
