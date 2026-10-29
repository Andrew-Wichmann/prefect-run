import functools
import inspect
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any, Literal, Optional, ParamSpec, TypeVar

from prefect import Flow, Task, flow

from joule import cache, trace

P = ParamSpec("P")
R = TypeVar("R")


class JobDefinitionError(RuntimeError):
    """A job ran different stages than it declared."""


@dataclass(frozen=True)
class Sla:
    """A delivery deadline: ``time`` (HH:MM) in ``tz`` on the close-of-business date plus ``day_offset`` days (T+1 is 1)."""

    time: str
    tz: str
    day_offset: int = 0


@dataclass(frozen=True)
class JobSpec:
    """Everything a job declares about itself; the audit UI reads this instead of keeping its own config."""

    retention: timedelta
    stages: list[str] = field(default_factory=list)
    sla: Sla | None = None
    duration_sla: float | None = None  # seconds the run may take
    iceberg_table: str | None = None


JOBS: dict[str, JobSpec] = {}
"""Every job's spec by flow name, filled in as job modules are imported."""


def job(
    *,
    retention: timedelta,
    stages: Sequence[Task[..., Any]],
    sla: Sla | None = None,
    duration_sla: float | None = None,
    iceberg_table: str | None = None,
    **flow_kwargs: Any,
) -> Callable[[Callable[P, R]], Flow[P, R]]:
    """Wrap a function as a Prefect flow.

    A job is always parameterized (``@job(retention=...)``, never bare ``@job``).
    ``retention`` is mandatory: how long the job keeps its stage results (its cache entries)
    after the last run that used them. Each use of an entry extends its expiry, and the daily
    ``cleanup-cache`` flow deletes entries that have expired; the audit log is never touched.
    ``stages`` is mandatory and non-empty: it declares, in order, the stages the job runs, and
    the run fails if it executes anything else. (A flow with no stages is a plain Prefect ``@flow``, not a job.) ``sla`` (delivery deadline), ``duration_sla`` (seconds the
    run may take) and ``iceberg_table`` describe the job; all are registered in ``JOBS``
    under the flow's name, which is where the audit UI reads them.

    A job also takes a ``bust_cache_from`` parameter: the name of a
    stage from which the cache is ignored, so that stage and all later ones rerun.
    """
    order = [s.name for s in stages]
    if not order:
        raise ValueError("a job must declare at least one stage; use a plain @flow otherwise")

    def decorate(f: Callable[P, R], /) -> Flow[P, R]:
        wrapped = flow(**flow_kwargs)(_with_cache_busting(f, order))
        JOBS[wrapped.name] = JobSpec(retention, order, sla, duration_sla, iceberg_table)
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
