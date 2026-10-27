"""Which stages a job run actually executed, so the job can check it against what it declared."""

import contextlib
import contextvars
from collections.abc import Iterator

_executed: contextvars.ContextVar[list[str] | None] = contextvars.ContextVar("joule_executed_stages", default=None)


@contextlib.contextmanager
def tracking() -> Iterator[list[str]]:
    """Within this block, ``note`` appends to the yielded list."""
    ran: list[str] = []
    token = _executed.set(ran)
    try:
        yield ran
    finally:
        _executed.reset(token)


def note(stage_name: str) -> None:
    ran = _executed.get()
    if ran is not None:
        ran.append(stage_name)
