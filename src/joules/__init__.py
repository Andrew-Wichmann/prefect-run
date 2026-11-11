"""The public API. Everything else (the job registry, cache, audit, serializer) is internal: import it from its module."""

from joules.job import JobDefinitionError, job
from joules.stage import PRIMARY_KEY, StageContractError, stage
from joules.status import Detail

__all__ = [
    "job", "stage",  # the two decorators: a job is a flow, a stage is a task
    "Detail", "PRIMARY_KEY",  # what a stage returns per row (a status string, optionally with a note), and the key column it must keep
    "JobDefinitionError", "StageContractError",  # raised when a job or stage breaks its contract
]
