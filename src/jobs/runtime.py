import json
import logging
import re
import threading
from datetime import datetime

from config.settings import settings
from jobs.types import (
    JobAwaitingApproval,
    JobCancelled,
    JobDefinition,
    NonRetryableJobError,
)
from repositories.job_repository import JobRepository
from security.redaction import redact_sensitive


logger = logging.getLogger(__name__)
_JOB_TYPE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]{0,99}$")


def _normalize_json(value, max_chars, label, require_mapping=False):
    if require_mapping and not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    safe_value = redact_sensitive(value)
    try:
        serialized = json.dumps(
            safe_value,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{label} must be JSON serializable") from exc
    if len(serialized) > int(max_chars):
        raise ValueError(
            f"{label} exceeds the {int(max_chars)} character limit"
        )
    return json.loads(serialized)


def _bounded_identifier(value, label, max_length):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if len(value) > max_length:
        raise ValueError(f"{label} exceeds {max_length} characters")
    return value


class JobContext:
    def __init__(self, repository, job, payload_limit):
        self.repository = repository
        self.job = job
        self._payload_limit = payload_limit

    @property
    def job_id(self):
        return self.job.id

    @property
    def approval_granted(self):
        return self.job.approval_granted is True

    def check_cancelled(self):
        if self.repository.is_cancel_requested(self.job.id):
            raise JobCancelled("Job cancellation requested")

    def set_progress(self, progress, data=None):
        safe_data = None
        if data is not None:
            safe_data = _normalize_json(
                data, self._payload_limit, "progress data"
            )
        if not self.repository.update_progress(
            self.job.id, progress, safe_data
        ):
            self.check_cancelled()
            raise RuntimeError("Job is no longer running")

    def require_approval(self, request):
        if self.approval_granted:
            return True
        safe_request = _normalize_json(
            request,
            self._payload_limit,
            "approval request",
            require_mapping=True,
        )
        raise JobAwaitingApproval(safe_request)


class JobWorker:
    def __init__(self, runtime, poll_interval):
        self.runtime = runtime
        self.poll_interval = max(0.05, float(poll_interval))
        self._stop = threading.Event()
        self._wake = threading.Event()
        self._thread = None
        self._lock = threading.Lock()

    @property
    def running(self):
        return self._thread is not None and self._thread.is_alive()

    def start(self):
        with self._lock:
            if self.running:
                return False
            self._stop.clear()
            self._thread = threading.Thread(
                target=self._run,
                name="aika-job-worker",
                daemon=True,
            )
            self._thread.start()
            return True

    def wake(self):
        self._wake.set()

    def _run(self):
        while not self._stop.is_set():
            try:
                handled = self.runtime.run_once()
            except Exception as exc:
                logger.error(
                    "Background job polling failed: %s", type(exc).__name__
                )
                handled = False
            if handled:
                continue
            self._wake.wait(self.poll_interval)
            self._wake.clear()

    def close(self, wait=True):
        self._stop.set()
        self._wake.set()
        thread = self._thread
        if wait and thread is not None:
            thread.join(timeout=5)


class JobRuntime:
    """Registered job handlers backed by durable PostgreSQL state."""

    def __init__(
        self,
        repository=None,
        *,
        poll_interval=None,
        payload_max_chars=None,
        result_max_chars=None,
        default_max_attempts=None,
        retry_delay_seconds=None,
        autostart=False,
    ):
        self.repository = repository or JobRepository()
        self.payload_max_chars = int(
            payload_max_chars
            if payload_max_chars is not None
            else settings.job_payload_max_chars
        )
        self.result_max_chars = int(
            result_max_chars
            if result_max_chars is not None
            else settings.job_result_max_chars
        )
        self.default_max_attempts = int(
            default_max_attempts
            if default_max_attempts is not None
            else settings.job_default_max_attempts
        )
        self.retry_delay_seconds = float(
            retry_delay_seconds
            if retry_delay_seconds is not None
            else settings.job_retry_delay_seconds
        )
        if self.payload_max_chars <= 0 or self.result_max_chars <= 0:
            raise ValueError("job payload and result limits must be positive")
        if self.default_max_attempts <= 0 or self.retry_delay_seconds < 0:
            raise ValueError("job retry settings are invalid")

        self._definitions = {}
        self._lock = threading.RLock()
        self._started = False
        self._closed = False
        self.worker = JobWorker(
            self,
            poll_interval=(
                poll_interval
                if poll_interval is not None
                else settings.job_worker_poll_interval
            ),
        )
        if autostart:
            self.start()

    @property
    def running(self):
        return self.worker.running

    def register(self, definition):
        if not isinstance(definition, JobDefinition):
            raise TypeError("definition must be a JobDefinition")
        if (
            not isinstance(definition.name, str)
            or not _JOB_TYPE_PATTERN.fullmatch(definition.name)
        ):
            raise ValueError("job type must be a lowercase dotted identifier")
        if not callable(definition.handler):
            raise ValueError("job handler must be callable")
        if definition.validator is not None and not callable(definition.validator):
            raise ValueError("job validator must be callable")
        if definition.max_attempts is not None and (
            isinstance(definition.max_attempts, bool)
            or not isinstance(definition.max_attempts, int)
            or definition.max_attempts <= 0
        ):
            raise ValueError("job max_attempts must be a positive integer")
        with self._lock:
            if self._closed:
                raise RuntimeError("job runtime is closed")
            if definition.name in self._definitions:
                raise ValueError(f"job type already registered: {definition.name}")
            self._definitions[definition.name] = definition
        self.worker.wake()

    def _definition(self, job_type):
        with self._lock:
            return self._definitions.get(job_type)

    def _registered_types(self):
        with self._lock:
            return tuple(self._definitions)

    def start(self):
        with self._lock:
            if self._closed:
                raise RuntimeError("job runtime is closed")
            if self._started:
                return False
            retry_safe_types = {
                name
                for name, definition in self._definitions.items()
                if definition.retry_safe
            }
            self.repository.recover_interrupted(retry_safe_types)
            self._started = True
        self.worker.start()
        return True

    def enqueue(
        self,
        job_type,
        payload,
        *,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
        available_at=None,
    ):
        if self._closed:
            raise RuntimeError("job runtime is closed")
        definition = self._definition(job_type)
        if definition is None:
            raise ValueError(f"unregistered job type: {job_type}")
        safe_payload = _normalize_json(
            payload,
            self.payload_max_chars,
            "job payload",
            require_mapping=True,
        )
        if definition.validator is not None:
            validated = definition.validator(safe_payload)
            safe_payload = _normalize_json(
                safe_payload if validated is None else validated,
                self.payload_max_chars,
                "validated job payload",
                require_mapping=True,
            )
        if available_at is not None and (
            not isinstance(available_at, datetime)
            or available_at.tzinfo is None
            or available_at.utcoffset() is None
        ):
            raise ValueError("available_at must be a timezone-aware datetime")
        max_attempts = definition.max_attempts or self.default_max_attempts
        safe_owner_id = _bounded_identifier(owner_id, "owner_id", 100)
        safe_agent_id = _bounded_identifier(agent_id, "agent_id", 50)
        safe_session_id = _bounded_identifier(session_id, "session_id", 50)
        job, created = self.repository.enqueue(
            job_type,
            safe_payload,
            max_attempts=max_attempts,
            owner_id=safe_owner_id,
            agent_id=safe_agent_id,
            session_id=safe_session_id,
            idempotency_key=_bounded_identifier(
                idempotency_key, "idempotency_key", 200
            ),
            available_at=available_at,
        )
        if not created and (
            job.job_type != job_type
            or job.owner_id != safe_owner_id
            or job.agent_id != safe_agent_id
        ):
            raise ValueError(
                "idempotency key belongs to a different job scope"
            )
        if created:
            self.worker.wake()
        return self._job_to_dict(job), created

    def run_once(self):
        job = self.repository.claim_next(self._registered_types())
        if job is None:
            return False
        definition = self._definition(job.job_type)
        if definition is None:
            self.repository.fail(
                job.id,
                "UnregisteredJobType",
                retryable=False,
                retry_delay_seconds=self.retry_delay_seconds,
            )
            return True

        context = JobContext(self.repository, job, self.payload_max_chars)
        try:
            context.check_cancelled()
            result = definition.handler(context, job.payload)
            context.check_cancelled()
            if result is None:
                result = {}
            safe_result = _normalize_json(
                result, self.result_max_chars, "job result"
            )
            self.repository.complete(job.id, safe_result)
        except JobAwaitingApproval as exc:
            self.repository.wait_for_approval(job.id, exc.request)
        except JobCancelled:
            self.repository.mark_cancelled(job.id)
        except Exception as exc:
            retryable = (
                definition.retry_safe
                and not isinstance(exc, NonRetryableJobError)
            )
            logger.error(
                "Background job %s failed: %s",
                job.id,
                type(exc).__name__,
            )
            self.repository.fail(
                job.id,
                type(exc).__name__,
                retryable=retryable,
                retry_delay_seconds=self.retry_delay_seconds,
            )
        return True

    def get_job(self, job_id):
        job = self.repository.get(str(job_id))
        return self._job_to_dict(job) if job is not None else None

    def list_jobs(self, **filters):
        return [
            self._job_to_dict(job)
            for job in self.repository.list_jobs(**filters)
        ]

    def get_job_events(self, job_id, limit=200):
        return [
            {
                "id": event.id,
                "job_id": event.job_id,
                "type": event.event_type,
                "data": event.data,
                "created_at": event.created_at.isoformat(),
            }
            for event in self.repository.list_events(str(job_id), limit=limit)
        ]

    def cancel_job(self, job_id):
        changed = self.repository.request_cancel(str(job_id))
        if changed:
            self.worker.wake()
        return changed

    def resolve_job_approval(self, job_id, approved):
        changed = self.repository.resolve_approval(str(job_id), bool(approved))
        if changed:
            self.worker.wake()
        return changed

    @staticmethod
    def _job_to_dict(job):
        timestamp_names = (
            "available_at", "created_at", "updated_at",
            "started_at", "finished_at",
        )
        data = {
            "id": job.id,
            "type": job.job_type,
            "payload": job.payload,
            "status": job.status,
            "owner_id": job.owner_id,
            "agent_id": job.agent_id,
            "session_id": job.session_id,
            "idempotency_key": job.idempotency_key,
            "progress": job.progress,
            "attempt_count": job.attempt_count,
            "max_attempts": job.max_attempts,
            "result": job.result,
            "error_type": job.error_type,
            "cancel_requested": job.cancel_requested,
            "approval_request": job.approval_request,
            "approval_granted": job.approval_granted,
        }
        for name in timestamp_names:
            value = getattr(job, name)
            data[name] = value.isoformat() if value is not None else None
        return data

    def close(self, wait=True):
        with self._lock:
            if self._closed:
                return
            self._closed = True
        self.worker.close(wait=wait)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(wait=True)
