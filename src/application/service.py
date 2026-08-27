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

    def __init__(
        self,
        brain=None,
        job_runtime=None,
        enable_jobs=False,
        reminder_scheduler=None,
        enable_reminders=False,
        persistent_orchestrator=None,
        enable_orchestration=False,
    ):
        if brain is None:
            from brain.brain import AikaBrain

            brain = AikaBrain()
        self.brain = brain
        self._lock = threading.Lock()
        self._brain_execution_lock = threading.RLock()
        self._thread_context = threading.local()
        self._active: Optional[_Operation] = None
        self._closed = False
        self._confirmations = ConfirmationCoordinator()
        set_execution_lock = getattr(self.brain, "set_execution_lock", None)
        if callable(set_execution_lock):
            set_execution_lock(self._brain_execution_lock)
        tool_manager = getattr(self.brain, "tool_manager", None)
        if tool_manager is not None:
            tool_manager.set_confirmation_handler(self._request_confirmation)
            tool_manager.set_event_handler(self._handle_tool_event)

        durable_runtime_enabled = (
            enable_jobs or enable_reminders or enable_orchestration
        )
        if durable_runtime_enabled and job_runtime is None:
            from jobs.runtime import JobRuntime

            job_runtime = JobRuntime(autostart=False)
        self.job_runtime = job_runtime
        if enable_reminders and reminder_scheduler is None:
            from reminders.scheduler import ReminderScheduler

            reminder_scheduler = ReminderScheduler(job_runtime)
            reminder_scheduler.start()
        self.reminder_scheduler = reminder_scheduler
        if enable_orchestration and persistent_orchestrator is None:
            from orchestration.runtime import PersistentOrchestrator

            persistent_orchestrator = PersistentOrchestrator(
                job_runtime,
                self.brain.agent_registry,
                self._execute_orchestration_step,
            )
            persistent_orchestrator.start()
        self.persistent_orchestrator = persistent_orchestrator

        if tool_manager is not None:
            if self.reminder_scheduler is not None:
                from tools.reminder_tool import ReminderTool

                tool_manager.register_tool(ReminderTool(self))

        if (
            durable_runtime_enabled
            and self.job_runtime is not None
            and not self.job_runtime.running
        ):
            self.job_runtime.start()
        if self.persistent_orchestrator is not None and durable_runtime_enabled:
            self.persistent_orchestrator.reconcile()

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

    def _stream_brain_serialized(self, user_input, cancel_event=None):
        with self._brain_execution_lock:
            if cancel_event is not None and cancel_event.is_set():
                return
            yield from self.brain.process_stream(user_input)

    def _execute_orchestration_step(
        self, agent_id, input_text, *, allow_high_tools=False
    ):
        with self._brain_execution_lock:
            with self._lock:
                if self._closed:
                    raise RuntimeError("AIKA service is closed")
            tool_manager = getattr(self.brain, "tool_manager", None)
            if tool_manager is not None:
                tool_manager.set_high_permission_policy(
                    lambda _name, _parameters: bool(allow_high_tools)
                )
            try:
                return self.brain.agent_loop.run(
                    input_text, agent_id=agent_id
                )
            finally:
                if tool_manager is not None:
                    tool_manager.set_high_permission_policy(None)

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
            for chunk in self._stream_brain_serialized(
                user_input, operation.cancelled
            ):
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
                elif getattr(
                    self.brain, "last_stream_status", None
                ) == "llm_error":
                    error_type = str(
                        getattr(
                            self.brain,
                            "last_stream_error_type",
                            "StreamError",
                        )
                        or "StreamError"
                    )
                    if not error_type.isidentifier():
                        error_type = "StreamError"
                    self._event(
                        operation,
                        AikaEventType.ERROR,
                        error="AIKA response was interrupted",
                        error_type=error_type[:80],
                        already_reported=True,
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
            self._thread_context.operation = None
            with self._lock:
                if self._active is operation:
                    self._active = None
            operation.events.put(_END)

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
            agent_id=self.current_agent_id,
            limit=limit,
        )
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
            "jobs_enabled": self.job_runtime is not None,
            "job_worker_running": bool(
                self.job_runtime is not None and self.job_runtime.running
            ),
            "reminders_enabled": self.reminder_scheduler is not None,
            "orchestration_enabled": self.persistent_orchestrator is not None,
        }
        if include_models:
            status["models"] = self.get_models()
        return status

    def register_job(self, definition):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        return self.job_runtime.register(definition)

    def enqueue_job(self, job_type, payload, **metadata):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        metadata.setdefault("agent_id", self.current_agent_id)
        metadata.setdefault("session_id", self.current_session_id)
        return self.job_runtime.enqueue(job_type, payload, **metadata)

    def get_job(self, job_id):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        return self.job_runtime.get_job(job_id)

    def get_jobs(self, **filters):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        return self.job_runtime.list_jobs(**filters)

    def get_job_events(self, job_id, limit=200):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        return self.job_runtime.get_job_events(job_id, limit=limit)

    def cancel_job(self, job_id):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        return self.job_runtime.cancel_job(job_id)

    def resolve_job_approval(self, job_id, approved):
        if self.job_runtime is None:
            raise RuntimeError("durable jobs are not enabled")
        return self.job_runtime.resolve_job_approval(job_id, approved)

    def create_reminder(self, message, scheduled_for, **options):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        options.setdefault("agent_id", self.current_agent_id)
        options.setdefault("session_id", self.current_session_id)
        return self.reminder_scheduler.create_reminder(
            message, scheduled_for, **options
        )

    def get_reminder(self, reminder_id, owner_id=None):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        return self.reminder_scheduler.get_reminder(
            reminder_id,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
        )

    def get_reminders(self, owner_id=None, **filters):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        filters.setdefault("owner_id", owner_id)
        filters.setdefault("agent_id", self.current_agent_id)
        return self.reminder_scheduler.list_reminders(**filters)

    def get_due_reminders(self, owner_id=None, limit=100):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        return self.reminder_scheduler.get_due_reminders(
            owner_id=owner_id,
            agent_id=self.current_agent_id,
            limit=limit,
        )

    def acknowledge_reminder(self, occurrence_id, owner_id=None):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        return self.reminder_scheduler.acknowledge_reminder(
            occurrence_id,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
        )

    def cancel_reminder(self, reminder_id, owner_id=None):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        return self.reminder_scheduler.cancel_reminder(
            reminder_id,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
        )

    def reschedule_reminder(
        self, reminder_id, scheduled_for, owner_id=None, **options
    ):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        options.setdefault("owner_id", owner_id)
        options.setdefault("agent_id", self.current_agent_id)
        return self.reminder_scheduler.reschedule_reminder(
            reminder_id, scheduled_for, **options
        )

    def set_reminder_handler(self, handler):
        if self.reminder_scheduler is None:
            raise RuntimeError("reminders are not enabled")
        return self.reminder_scheduler.set_notification_handler(handler)

    def create_orchestration(self, kind, agent_ids, task, **options):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        options.setdefault("agent_id", self.current_agent_id)
        options.setdefault("session_id", self.current_session_id)
        return self.persistent_orchestrator.create_run(
            kind, agent_ids, task, **options
        )

    def get_orchestration(self, run_id, owner_id=None, include_steps=True):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        return self.persistent_orchestrator.get_run(
            run_id,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
            include_steps=include_steps,
        )

    def get_orchestrations(self, owner_id=None, **filters):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        filters.setdefault("owner_id", owner_id)
        filters.setdefault("agent_id", self.current_agent_id)
        return self.persistent_orchestrator.list_runs(**filters)

    def cancel_orchestration(self, run_id, owner_id=None):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        return self.persistent_orchestrator.cancel_run(
            run_id,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
        )

    def resolve_orchestration_approval(
        self, run_id, approved, owner_id=None
    ):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        return self.persistent_orchestrator.resolve_approval(
            run_id,
            approved,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
        )

    def resume_orchestration(self, run_id, owner_id=None):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        return self.persistent_orchestrator.resume_run(
            run_id,
            owner_id=owner_id,
            agent_id=self.current_agent_id,
        )

    def set_orchestration_handler(self, handler):
        if self.persistent_orchestrator is None:
            raise RuntimeError("persistent orchestration is not enabled")
        return self.persistent_orchestrator.set_notification_handler(handler)

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
            tool_manager.set_high_permission_policy(None)

        if self.reminder_scheduler is not None:
            self.reminder_scheduler.set_notification_handler(None)
        if self.persistent_orchestrator is not None:
            self.persistent_orchestrator.set_notification_handler(None)
        if self.job_runtime is not None:
            self.job_runtime.close(wait=wait)
        if wait:
            with self._brain_execution_lock:
                self.brain.close(wait=wait)
        else:
            self.brain.close(wait=wait)
        if wait and operation is not None and operation.thread is not None:
            operation.thread.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(wait=True)
