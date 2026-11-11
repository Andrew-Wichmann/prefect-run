Detail = str | tuple[str, str]
"""What a stage reports for one row: a status, or ``(status, note)`` to explain it. A status is any non-empty
string; the framework has no list of them, so a job names its own."""


def valid_detail(detail: object) -> bool:
    status, note = detail if isinstance(detail, tuple) and len(detail) == 2 else (detail, None)
    return isinstance(status, str) and bool(status) and (note is None or isinstance(note, str))


def split_detail(detail: Detail) -> tuple[str, str | None]:
    """``(status, note or None)`` for an already validated detail."""
    return detail if isinstance(detail, tuple) else (detail, None)
