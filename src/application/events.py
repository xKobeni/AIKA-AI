from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class AikaEventType(str, Enum):
    STATUS = "status"
    TEXT_DELTA = "text_delta"
    TOOL_REQUEST = "tool_request"
    APPROVAL_REQUIRED = "approval_required"
    TOOL_RESULT = "tool_result"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


@dataclass(frozen=True)
class AikaEvent:
    type: AikaEventType
    operation_id: str
    data: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "type": self.type.value,
            "operation_id": self.operation_id,
            "data": dict(self.data),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(frozen=True)
class AikaResult:
    operation_id: str
    text: str
    events: tuple[AikaEvent, ...]
    completed: bool
    cancelled: bool = False
    error: Optional[str] = None
