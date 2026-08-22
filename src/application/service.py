from dataclasses import dataclass, field
import logging
from queue import Queue
import threading
import uuid
from typing import Callable, Iterator, Optional

from application.confirmation import ConfirmationCoordinator
from application.events import AikaEvent, AikaEventType, AikaResult


logger = logging.getLogger(__name__)
_END = object()


@dataclass
class _Operation:
    id: str
    events: Queue = field(default_factory=Queue)
    cancelled: threading.Event = field(default_factory=threading.Event)
    thread: Optional[threading.Thread] = None


class AikaService:
    """Thin, transport-neutral facade around the existing AikaBrain runtime."""

    def __init__(self, brain=None):
        if brain is None:
            from brain.brain import AikaBrain

            brain = AikaBrain()
        self.brain = brain
        self._lock = threading.Lock()
        self._thread_context = threading.local()
        self._active: Optional[_Operation] = None
        self._closed = False
        self._confirmations = ConfirmationCoordinator()

        tool_manager = getattr(self.brain, "tool_manager", None)
        if tool_manager is not None:
            tool_manager.set_confirmation_handler(self._request_confirmation)
            tool_manager.set_event_handler(self._handle_tool_event)

    @property
    def current_agent_id(self):
        return self.brain.current_agent_id

    @property
    def current_session_id(self):
        return self.brain.current_session.id

    @property
    def active_operation_id(self):
        with self._lock:
            return self._active.id if self._active is not None else None

    def _event(self, operation, event_type, **data):
        operation.events.put(AikaEvent(
            type=event_type,
            operation_id=operation.id,
            data=data,
        ))

    def _current_operation(self):
        return getattr(self._thread_context, "operation", None)

    def _handle_tool_event(self, event_type, payload):
        operation = self._current_operation()
        if operation is None:
            return
        mapping = {
            "tool_request": AikaEventType.TOOL_REQUEST,
            "tool_result": AikaEventType.TOOL_RESULT,
        }
        mapped_type = mapping.get(event_type)
        if mapped_type is not None:
            self._event(operation, mapped_type, **dict(payload))

    def _request_confirmation(self, tool_name, parameters):
        operation = self._current_operation()
        if operation is None or operation.cancelled.is_set():
            return False

        def publish(request):
            self._event(
                operation,
                AikaEventType.APPROVAL_REQUIRED,
                **request.to_dict(),
            )

        return self._confirmations.request(
            operation_id=operation.id,
            tool_name=tool_name,
            parameters=parameters,
            publish=publish,
            cancel_event=operation.cancelled,
        )

    def _run_operation(self, operation, user_input):
        self._thread_context.operation = operation
        self._event(
            operation,
            AikaEventType.STATUS,
            state="started",
            agent_id=self.current_agent_id,
            session_id=self.current_session_id,
        )
        try:
            for chunk in self.brain.process_stream(user_input):
                if operation.cancelled.is_set():
                    self._event(
                        operation, AikaEventType.CANCELLED, state="cancelled"
                    )
                    break
                if chunk:
                    self._event(
                        operation, AikaEventType.TEXT_DELTA, text=str(chunk)
                    )
            else:
                if operation.cancelled.is_set():
                    self._event(
                        operation, AikaEventType.CANCELLED, state="cancelled"
                    )
                else:
                    self._event(
                        operation,
                        AikaEventType.COMPLETED,
                        state="completed",
                        agent_id=self.current_agent_id,
                        session_id=self.current_session_id,
                    )
        except Exception as exc:
            logger.error(
                "AIKA operation %s failed: %s",
                operation.id,
                type(exc).__name__,
            )
            self._event(
                operation,
                AikaEventType.ERROR,
                error="AIKA operation failed",
                error_type=type(exc).__name__,
            )
        finally:
            self._confirmations.cancel_operation(operation.id)
            operation.events.put(_END)
            self._thread_context.operation = None
            with self._lock:
                if self._active is operation:
                    self._active = None

    def stream(self, user_input: str) -> Iterator[AikaEvent]:
        if not isinstance(user_input, str) or not user_input.strip():
            raise ValueError("user_input must be a non-empty string")

        with self._lock:
            if self._closed:
                raise RuntimeError("AIKA service is closed")
            if self._active is not None:
                raise RuntimeError("AIKA is already processing a request")
            operation = _Operation(id=uuid.uuid4().hex)
            self._active = operation

        operation.thread = threading.Thread(
            target=self._run_operation,
            args=(operation, user_input),
            name=f"aika-service-{operation.id[:8]}",
            daemon=True,
        )
        operation.thread.start()

        completed = False
        try:
            while True:
                item = operation.events.get()
                if item is _END:
                    completed = True
                    break
                yield item
        finally:
            if not completed and operation.thread.is_alive():
                operation.cancelled.set()
                self._confirmations.cancel_operation(operation.id)

    def submit(
        self,
        user_input: str,
        approval_handler: Optional[Callable[[AikaEvent], bool]] = None,
    ) -> AikaResult:
        events = []
        text_parts = []
        completed = False
        cancelled = False
        error = None
        operation_id = ""

        for event in self.stream(user_input):
            operation_id = event.operation_id
            events.append(event)
            if event.type == AikaEventType.TEXT_DELTA:
                text_parts.append(event.data.get("text", ""))
            elif event.type == AikaEventType.APPROVAL_REQUIRED:
                approved = False
                if approval_handler is not None:
                    try:
                        approved = bool(approval_handler(event))
                    except Exception:
                        approved = False
                self.resolve_confirmation(
                    event.data["confirmation_id"], approved
                )
            elif event.type == AikaEventType.COMPLETED:
                completed = True
            elif event.type == AikaEventType.CANCELLED:
                cancelled = True
            elif event.type == AikaEventType.ERROR:
                error = event.data.get("error", "AIKA operation failed")

        return AikaResult(
            operation_id=operation_id,
            text="".join(text_parts),
            events=tuple(events),
            completed=completed,
            cancelled=cancelled,
            error=error,
        )

    def resolve_confirmation(self, confirmation_id: str, approved: bool):
        return self._confirmations.resolve(confirmation_id, approved)

    def cancel_active(self):
        with self._lock:
            operation = self._active
        if operation is None:
            return False
        operation.cancelled.set()
        self._confirmations.cancel_operation(operation.id)
        return True

    def start_session(self):
        return self.submit("new session")

    def resume_session(self, session_id: str):
        session_id = str(session_id).strip()
        if not session_id or any(character.isspace() for character in session_id):
            raise ValueError("session_id must be a non-empty identifier")
        return self.submit(f"resume {session_id}")

    def get_sessions(self, limit=10):
        limit = max(1, min(int(limit), 100))
        sessions = self.brain.session_repo.get_all_sessions(
            agent_id=self.current_agent_id
        )[:limit]
        return [
            {
                "id": session.id,
                "agent_id": session.agent_id,
                "started_at": session.started_at.isoformat(),
                "last_active": session.last_active.isoformat(),
                "message_count": session.message_count,
                "summary": session.summary,
                "current": session.id == self.current_session_id,
            }
            for session in sessions
        ]

    def get_history(self, session_id=None, limit=50):
        limit = max(1, min(int(limit), 200))
        session_id = session_id or self.current_session_id
        conversations = self.brain.conversation_repo.get_by_session(
            session_id,
            limit=limit,
            agent_id=self.current_agent_id,
        )
        return [
            {
                "id": conversation.id,
                "role": conversation.role,
                "content": conversation.content,
                "tool_used": conversation.tool_used,
                "model_used": conversation.model_used,
                "created_at": conversation.created_at.isoformat(),
                "agent_id": conversation.agent_id,
            }
            for conversation in conversations
        ]

    def get_agents(self):
        return [
            {
                "id": profile.id,
                "name": profile.name,
                "model": profile.model,
                "allowed_tools": profile.allowed_tools,
                "max_iterations": profile.max_iterations,
                "is_active": profile.is_active,
                "role": profile.role,
                "delegates_to": profile.delegates_to,
            }
            for profile in self.brain.agent_registry.get_all()
        ]

    def get_models(self):
        return self.brain.llm.list_models()

    def get_status(self, include_models=False):
        status = {
            "closed": self._closed,
            "active_operation_id": self.active_operation_id,
            "agent_id": self.current_agent_id,
            "session_id": self.current_session_id,
            "configured_model": self.brain.llm.model,
        }
        if include_models:
            status["models"] = self.get_models()
        return status

    def close(self, wait=True):
        with self._lock:
            if self._closed:
                return
            self._closed = True
            operation = self._active

        if operation is not None:
            operation.cancelled.set()
            self._confirmations.cancel_operation(operation.id)
        self._confirmations.close()

        tool_manager = getattr(self.brain, "tool_manager", None)
        if tool_manager is not None:
            tool_manager.set_confirmation_handler(None)
            tool_manager.set_event_handler(None)

        self.brain.close(wait=wait)
        if wait and operation is not None and operation.thread is not None:
            operation.thread.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(wait=True)
