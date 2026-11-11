import functools
import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal, Optional, ParamSpec, TypeVar

from prefect import Flow, Task, flow

from joules import cache, trace

P = ParamSpec("P")
R = TypeVar("R")


class JobDefinitionError(RuntimeError):
    """A job's stages don't chain (one stage's output schema is not the next one's input schema), or it ran different stages than it declared."""


def _check_chain(stages: Sequence[Task[..., Any]]) -> None:
    """Each stage's ``out_schema`` must equal the next stage's ``in_schema`` (field names, order, types, nullability)."""
    for a, b in zip(stages, stages[1:]):
        out, into = getattr(a, "out_schema", None), getattr(b, "in_schema", None)
        if out is None or into is None:
            raise JobDefinitionError(f"{(a if out is None else b).name!r} is not a joules stage (use @stage)")
        if not out.equals(into, check_metadata=False):
            raise JobDefinitionError(
                f"stage {a.name!r} outputs a schema that stage {b.name!r} does not take.\n"
                f"{a.name} out_schema:\n{out}\n{b.name} in_schema:\n{into}"
            )


@dataclass(frozen=True)
class JobSpec:
    """Everything a job declares about itself; the audit UI reads this instead of keeping its own config."""

    retention: timedelta
    stages: list[str] = field(default_factory=list)
    iceberg_table: str | None = None


JOBS: dict[str, JobSpec] = {}
"""Every job's spec by flow name, filled in as job modules are imported."""


def job(
    *,
    retention: timedelta,
    stages: Sequence[Task[..., Any]],
    iceberg_table: str | None = None,
    **flow_kwargs: Any,
) -> Callable[[Callable[P, R]], Flow[P, R]]:
    """Wrap a function as a Prefect flow.

    A job is always parameterized (``@job(retention=...)``, never bare ``@job``).
    ``retention`` is mandatory: how long the job keeps its stage results (its cache entries)
    after the last run that used them. Each use of an entry extends its expiry, and the daily
    ``cleanup-cache`` flow deletes entries that have expired; the audit log is never touched.
    ``stages`` is mandatory and non-empty: it declares, in order, the stages the job runs, and
    the run fails if it executes anything else. Each stage's ``out_schema`` must equal the next one's ``in_schema``;
    this is checked when the job is defined (``JobDefinitionError``), before anything runs. (A flow with no stages is a plain Prefect ``@flow``, not a job.) ``iceberg_table`` describes the job; it is registered in ``JOBS``
    under the flow's name, which is where the audit UI reads it.

    A job also takes a ``bust_cache_from`` parameter: the name of a
    stage from which the cache is ignored, so that stage and all later ones rerun.
    """
    order = [s.name for s in stages]
    if not order:
        raise ValueError("a job must declare at least one stage; use a plain @flow otherwise")
    _check_chain(stages)

    def decorate(f: Callable[P, R], /) -> Flow[P, R]:
        wrapped = flow(**flow_kwargs)(_with_cache_busting(f, order))
        JOBS[wrapped.name] = JobSpec(retention, order, iceberg_table)
        return wrapped

    return decorate


def _with_cache_busting(f: Callable[..., Any], order: list[str]) -> Callable[..., Any]:
    """Add a ``bust_cache_from`` keyword parameter to a job function, and check it runs the stages it declared."""

    @functools.wraps(f)
    def run(*args: Any, bust_cache_from: str | None = None, **kwargs: Any) -> Any:
        with cache.bust_from(order, bust_cache_from), trace.tracking() as ran:
            result = f(*args, **kwargs)
        if ran != order:
            raise JobDefinitionError(f"job declares stages {order} but ran {ran}")
        return result

    sig = inspect.signature(f)
    extra = inspect.Parameter("bust_cache_from", inspect.Parameter.KEYWORD_ONLY, default=None, annotation=Optional[Literal[tuple(order)]])
    run.__signature__ = sig.replace(parameters=[*sig.parameters.values(), extra])  # type: ignore[attr-defined]
    return run
