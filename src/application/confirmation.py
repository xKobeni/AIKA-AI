from dataclasses import dataclass, field
import threading
import uuid
from typing import Any, Callable, Optional


@dataclass(frozen=True)
class ConfirmationRequest:
    id: str
    operation_id: str
    tool_name: str
    parameters: dict[str, Any]

    def to_dict(self):
        return {
            "confirmation_id": self.id,
            "tool_name": self.tool_name,
            "parameters": dict(self.parameters),
        }


@dataclass
class _PendingConfirmation:
    request: ConfirmationRequest
    resolved: threading.Event = field(default_factory=threading.Event)
    approved: bool = False


class ConfirmationCoordinator:
    """Coordinates approval without coupling tool execution to stdin."""

    def __init__(self):
        self._lock = threading.Lock()
        self._pending: dict[str, _PendingConfirmation] = {}
        self._closed = False

    def request(
        self,
        operation_id: str,
        tool_name: str,
        parameters: dict[str, Any],
        publish: Callable[[ConfirmationRequest], None],
        cancel_event: Optional[threading.Event] = None,
    ) -> bool:
        request = ConfirmationRequest(
            id=uuid.uuid4().hex,
            operation_id=operation_id,
            tool_name=tool_name,
            parameters=dict(parameters),
        )
        pending = _PendingConfirmation(request=request)
        with self._lock:
            if self._closed:
                return False
            self._pending[request.id] = pending

        publish(request)
        try:
            while not pending.resolved.wait(0.1):
                if cancel_event is not None and cancel_event.is_set():
                    return False
                with self._lock:
                    if self._closed:
                        return False
            return pending.approved
        finally:
            with self._lock:
                self._pending.pop(request.id, None)

    def resolve(self, confirmation_id: str, approved: bool) -> bool:
        with self._lock:
            pending = self._pending.get(confirmation_id)
            if pending is None or pending.resolved.is_set():
                return False
            pending.approved = bool(approved)
            pending.resolved.set()
            return True

    def cancel_operation(self, operation_id: str):
        with self._lock:
            pending = [
                item for item in self._pending.values()
                if item.request.operation_id == operation_id
            ]
            for item in pending:
                item.approved = False
                item.resolved.set()

    def close(self):
        with self._lock:
            self._closed = True
            pending = list(self._pending.values())
            for item in pending:
                item.approved = False
                item.resolved.set()
