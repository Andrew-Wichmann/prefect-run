"""The public API. Everything else (the job registry, cache, audit, serializer) is internal: import it from its module."""

from joule.job import JobDefinitionError, Link, Sla, job, link
from joule.stage import PRIMARY_KEY, StageContractError, stage
from joule.status import Outcome, Status

__all__ = [
    "job", "stage",  # the two decorators: a job is a flow, a stage is a task
    "Status", "Outcome", "PRIMARY_KEY",  # what a stage returns per row, and the key column it must keep
    "Sla", "Link", "link",  # job options and the link a run can attach to its card
    "JobDefinitionError", "StageContractError",  # raised when a job or stage breaks its contract
]
