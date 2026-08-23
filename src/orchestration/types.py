from enum import Enum


class OrchestrationKind(str, Enum):
    DELEGATE = "delegate"
    CHAIN = "chain"
    PARALLEL = "parallel"
    TEAM = "team"


class OrchestrationStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    WAITING_APPROVAL = "waiting_approval"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class OrchestrationStepStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
