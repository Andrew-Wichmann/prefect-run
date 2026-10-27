"""Cross-run caching for stages: same stage, same code, same inputs -> reuse the earlier result.

A run can bust the cache from a given stage onwards: that stage and every stage after it
in the job recompute (and refresh what is cached), even if their inputs are unchanged.
"""

import contextlib
import contextvars
import inspect
import os
import sysconfig
import types
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
from prefect.cache_policies import CachePolicy
from prefect.context import TaskRunContext
from prefect.utilities.hashing import hash_objects

_busted: contextvars.ContextVar[frozenset[str]] = contextvars.ContextVar("joule_busted_stages", default=frozenset())


def _canonical(value: Any) -> Any:
    """Tables hash by content: pickling a table also captures its chunk layout, which differs
    between a freshly computed table and an identical one read back from the cache."""
    if isinstance(value, pa.Table):
        value = value.combine_chunks()
        sink = pa.BufferOutputStream()
        with pa.ipc.new_stream(sink, value.schema) as writer:
            writer.write_table(value)
        return sink.getvalue().to_pybytes()
    return value


_LIBRARY_ROOTS = [Path(p) for k in ("stdlib", "platstdlib", "purelib", "platlib") if (p := sysconfig.get_paths().get(k))]
_CONSTANTS = (str, bytes, int, float, bool, list, tuple, dict, pa.Schema, pa.DataType)


def _first_party(obj: Any) -> bool:
    """Code of ours (a stage, a helper), as opposed to the standard library or an installed package."""
    file = getattr(inspect.getmodule(obj), "__file__", None)
    return bool(file) and not any(Path(file).is_relative_to(root) for root in _LIBRARY_ROOTS)


def _names(code: types.CodeType) -> Iterator[str]:
    yield from code.co_names
    for const in code.co_consts:
        if isinstance(const, types.CodeType):
            yield from _names(const)


def fingerprint(fn: Callable[..., Any]) -> str:
    """The stage's source plus everything of ours it uses: helper functions and classes (followed
    transitively), the source of any of our modules it references, and the value of module-level
    constants (schemas, reason lists), so editing any of them invalidates the stage's cache.
    Standard-library and installed packages are not tracked; bump the stage if you upgrade one."""
    parts: dict[str, str] = {}

    def visit(f: Callable[..., Any]) -> None:
        key = f"{f.__module__}.{f.__qualname__}"
        if key in parts:
            return
        try:
            parts[key] = inspect.getsource(f)
        except (OSError, TypeError):
            parts[key] = ""
        parts[key] += f"\n# defaults: {f.__defaults__!r} {f.__kwdefaults__!r}"  # evaluated at definition, so not in the code's names
        for name in sorted(set(_names(f.__code__))):
            value = f.__globals__.get(name)
            if isinstance(value, types.FunctionType) and _first_party(value):
                visit(value)
            elif isinstance(value, type) and _first_party(value):
                parts.setdefault(f"{value.__module__}.{value.__qualname__}", inspect.getsource(value))
            elif isinstance(value, types.ModuleType) and _first_party(value):
                parts.setdefault(value.__name__, inspect.getsource(value))
            elif isinstance(value, _CONSTANTS):
                parts.setdefault(f"{f.__module__}:{name}", repr(value) if not isinstance(value, pa.Schema) else str(value))

    visit(fn)
    return "\n".join(f"# {k}\n{parts[k]}" for k in sorted(parts))


@dataclass
class StageInputs(CachePolicy):
    """Cache on a stage's inputs, plus its name and source.

    The name keeps different stages apart (two stages given the same table must not share an
    entry), and the source (see ``fingerprint``) means editing a stage's code, or the helpers and
    constants it uses, invalidates its cache."""

    name: str = ""
    source: str = ""

    def compute_key(
        self, task_ctx: TaskRunContext, inputs: dict[str, Any], flow_parameters: dict[str, Any], **kwargs: Any
    ) -> str | None:
        return hash_objects(
            self.name, self.source, {k: _canonical(v) for k, v in inputs.items()}, raise_on_failure=True
        )


def policy_for(name: str, fn: Callable[..., Any], *schemas: pa.Schema) -> CachePolicy:
    """Cache on the stage's inputs (and identity: its code, helpers, constants and schemas)."""
    # key_storage makes Prefect write its per-entry metadata to a separate directory, so the result
    # file itself is the raw Parquet from ParquetSerializer rather than a JSON envelope around it.
    root = os.environ.get("PREFECT_LOCAL_STORAGE_PATH") or str(Path.home() / ".prefect" / "storage")
    return StageInputs(
        name=name, source="\n".join([fingerprint(fn), *map(str, schemas)]), key_storage=str(Path(root) / "_meta")
    )


def is_busted(stage_name: str) -> bool:
    return stage_name in _busted.get()


@contextlib.contextmanager
def bust_from(order: Sequence[str], stage_name: str | None) -> Iterator[None]:
    """Within this block, ``stage_name`` and every stage after it in ``order`` ignore the cache."""
    if stage_name is None:
        yield
        return
    if stage_name not in order:
        raise ValueError(f"cannot bust cache from {stage_name!r}: not one of this job's stages {list(order)}")
    token = _busted.set(frozenset(order[list(order).index(stage_name) :]))
    try:
        yield
    finally:
        _busted.reset(token)
