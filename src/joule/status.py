from enum import Enum


class Status(str, Enum):
    """Outcome of a stage for a single row."""

    INIT = "init"
    PASSED = "passed"
    CALIBRATED = "calibrated"
    STRESSED = "stressed"
    UPLOADED = "uploaded"
    FAILED = "failed"


Outcome = Status | tuple[Status, str]
"""What a stage reports for one row: a ``Status``, or ``(Status, detail)`` to explain it."""


def split_outcome(outcome: Outcome) -> tuple[str, str | None]:
    """``(status value, detail or None)`` for an already validated outcome."""
    if isinstance(outcome, tuple):
        status, detail = outcome
        return Status(status).value, detail
    return Status(outcome).value, None
