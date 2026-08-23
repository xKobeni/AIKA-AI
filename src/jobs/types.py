from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobCancelled(RuntimeError):
    pass


class JobAwaitingApproval(RuntimeError):
    def __init__(self, request):
        super().__init__("Job is waiting for approval")
        self.request = request


class NonRetryableJobError(RuntimeError):
    pass


@dataclass(frozen=True)
class JobDefinition:
    name: str
    handler: Callable
    validator: Optional[Callable] = None
    retry_safe: bool = False
    max_attempts: Optional[int] = None
