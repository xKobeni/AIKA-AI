from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class AgentMessage:
    from_agent: str
    to_agent: str
    message_type: str
    payload: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    session_id: Optional[str] = None
    parent_message_id: Optional[str] = None

    def to_dict(self):
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "payload": self.payload,
            "timestamp": self.timestamp,
            "session_id": self.session_id,
            "parent_message_id": self.parent_message_id,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            from_agent=data["from_agent"],
            to_agent=data["to_agent"],
            message_type=data["message_type"],
            payload=data.get("payload", {}),
            timestamp=data.get("timestamp"),
            session_id=data.get("session_id"),
            parent_message_id=data.get("parent_message_id"),
        )

    @classmethod
    def task(cls, from_agent, to_agent, task_description, context=None):
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type="task",
            payload={
                "task": task_description,
                "context": context or {}
            }
        )

    @classmethod
    def result(cls, from_agent, to_agent, result_data, success=True):
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type="result",
            payload={
                "result": result_data,
                "success": success
            }
        )

    @classmethod
    def handoff(cls, from_agent, to_agent, context):
        return cls(
            from_agent=from_agent,
            to_agent=to_agent,
            message_type="handoff",
            payload={"context": context}
        )
