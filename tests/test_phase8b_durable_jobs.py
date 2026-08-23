from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest


class FakeJobRepository:
    def __init__(self):
        self.jobs = {}
        self.events = {}
        self.recovery_calls = []

    def _event(self, job, event_type, data=None):
        events = self.events.setdefault(job.id, [])
        events.append(SimpleNamespace(
            id=len(events) + 1,
            job_id=job.id,
            event_type=event_type,
            data=data or {},
            created_at=datetime.now(timezone.utc),
        ))

    def enqueue(
        self,
        job_type,
        payload,
        *,
        max_attempts,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
        available_at=None,
    ):
        if idempotency_key:
            for existing in self.jobs.values():
                if existing.idempotency_key == idempotency_key:
                    return existing, False
        now = datetime.now(timezone.utc)
        job = SimpleNamespace(
            id=uuid.uuid4().hex,
            job_type=job_type,
            payload=payload,
            status="queued",
            owner_id=owner_id,
            agent_id=agent_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            progress=0,
            attempt_count=0,
            max_attempts=max_attempts,
            result=None,
            error_type=None,
            cancel_requested=False,
            approval_request=None,
            approval_granted=None,
            available_at=available_at or now,
            created_at=now,
            updated_at=now,
            started_at=None,
            finished_at=None,
        )
        self.jobs[job.id] = job
        self._event(job, "queued")
        return job, True

    def claim_next(self, registered_types, now=None):
        for job in self.jobs.values():
            if job.status == "queued" and job.job_type in registered_types:
                job.status = "running"
                job.attempt_count += 1
                job.started_at = datetime.now(timezone.utc)
                self._event(job, "started", {"attempt": job.attempt_count})
                return job
        return None

    def update_progress(self, job_id, progress, data=None):
        job = self.jobs[job_id]
        if job.status != "running":
            return False
        job.progress = int(progress)
        self._event(job, "progress", {"progress": progress, "data": data})
        return True

    def complete(self, job_id, result):
        job = self.jobs[job_id]
        if job.cancel_requested:
            self.mark_cancelled(job_id)
            return False
        job.status = "succeeded"
        job.result = result
        job.progress = 100
        job.finished_at = datetime.now(timezone.utc)
        self._event(job, "succeeded")
        return True

    def fail(self, job_id, error_type, *, retryable, retry_delay_seconds):
        job = self.jobs[job_id]
        job.error_type = error_type
        if retryable and job.attempt_count < job.max_attempts:
            job.status = "queued"
            self._event(job, "retry_scheduled")
        else:
            job.status = "failed"
            job.finished_at = datetime.now(timezone.utc)
            self._event(job, "failed", {"error_type": error_type})
        return job.status

    def request_cancel(self, job_id):
        job = self.jobs.get(job_id)
        if job is None or job.status in {"succeeded", "failed", "cancelled"}:
            return False
        job.cancel_requested = True
        if job.status in {"queued", "waiting_approval"}:
            self.mark_cancelled(job_id)
        else:
            self._event(job, "cancellation_requested")
        return True

    def is_cancel_requested(self, job_id):
        job = self.jobs.get(job_id)
        return job is None or job.cancel_requested

    def mark_cancelled(self, job_id):
        job = self.jobs[job_id]
        if job.status == "cancelled":
            return False
        job.status = "cancelled"
        job.cancel_requested = True
        job.finished_at = datetime.now(timezone.utc)
        self._event(job, "cancelled")
        return True

    def wait_for_approval(self, job_id, request):
        job = self.jobs[job_id]
        job.status = "waiting_approval"
        job.attempt_count = max(0, job.attempt_count - 1)
        job.approval_request = request
        job.approval_granted = None
        self._event(job, "approval_required", request)
        return True

    def resolve_approval(self, job_id, approved):
        job = self.jobs.get(job_id)
        if job is None or job.status != "waiting_approval":
            return False
        job.approval_granted = bool(approved)
        self._event(job, "approval_resolved", {"approved": bool(approved)})
        if approved:
            if job.attempt_count < job.max_attempts:
                job.status = "queued"
            else:
                job.status = "failed"
                job.error_type = "JobAttemptLimitExceeded"
        else:
            self.mark_cancelled(job_id)
        return True

    def get(self, job_id):
        return self.jobs.get(job_id)

    def list_jobs(self, **filters):
        jobs = list(self.jobs.values())
        for name, value in filters.items():
            if name == "limit":
                continue
            jobs = [job for job in jobs if getattr(job, name) == value]
        return jobs[:filters.get("limit", 50)]

    def list_events(self, job_id, limit=200):
        return self.events.get(job_id, [])[:limit]

    def recover_interrupted(self, retry_safe_types):
        self.recovery_calls.append(set(retry_safe_types))
        result = {
            "requeued": 0,
            "waiting_approval": 0,
            "cancelled": 0,
            "failed": 0,
        }
        for job in self.jobs.values():
            if job.status != "running":
                continue
            if job.cancel_requested:
                self.mark_cancelled(job.id)
                result["cancelled"] += 1
            elif job.attempt_count >= job.max_attempts:
                job.status = "failed"
                job.error_type = "JobAttemptLimitExceeded"
                result["failed"] += 1
            elif job.job_type in retry_safe_types:
                job.status = "queued"
                result["requeued"] += 1
            else:
                job.status = "waiting_approval"
                job.approval_request = {"reason": "interrupted_job"}
                result["waiting_approval"] += 1
        return result


def _runtime(repository=None, **kwargs):
    from jobs.runtime import JobRuntime

    return JobRuntime(
        repository=repository or FakeJobRepository(),
        poll_interval=0.05,
        retry_delay_seconds=0,
        **kwargs,
    )


def test_job_models_and_migration_define_durable_state_constraints():
    from database.models import Job, JobEvent
    from database.migrations import MIGRATIONS

    unique_constraints = {
        constraint.name for constraint in Job.__table__.constraints
    }
    assert "uq_jobs_idempotency_key" in unique_constraints
    event_fk = next(iter(JobEvent.__table__.c.job_id.foreign_keys))
    assert event_fk.target_fullname == "jobs.id"
    assert event_fk.ondelete == "CASCADE"
    durable_job_migration = next(
        migration for migration in MIGRATIONS if migration.version == 3
    )
    assert durable_job_migration.name == "durable background jobs"


def test_registered_job_runs_with_progress_redaction_and_result():
    from jobs.types import JobDefinition

    repository = FakeJobRepository()
    runtime = _runtime(repository)

    def handler(context, payload):
        context.set_progress(40, {"token": "do-not-store"})
        return {"echo": payload["name"], "password": "do-not-store"}

    runtime.register(JobDefinition("test.echo", handler))
    created, was_created = runtime.enqueue(
        "test.echo",
        {"name": "AIKA", "api_key": "do-not-store"},
        owner_id="user-1",
    )

    assert was_created is True
    assert created["payload"]["api_key"] == "[REDACTED]"
    assert runtime.run_once() is True
    completed = runtime.get_job(created["id"])
    assert completed["status"] == "succeeded"
    assert completed["progress"] == 100
    assert completed["result"] == {
        "echo": "AIKA",
        "password": "[REDACTED]",
    }
    events = runtime.get_job_events(created["id"])
    progress = next(event for event in events if event["type"] == "progress")
    assert progress["data"]["data"]["token"] == "[REDACTED]"


def test_idempotency_key_returns_existing_job_without_duplicate_execution():
    from jobs.types import JobDefinition

    runtime = _runtime()
    runtime.register(JobDefinition("test.once", lambda context, payload: payload))

    first, first_created = runtime.enqueue(
        "test.once", {"value": 1}, idempotency_key="request-1"
    )
    second, second_created = runtime.enqueue(
        "test.once", {"value": 2}, idempotency_key="request-1"
    )

    assert first_created is True
    assert second_created is False
    assert second["id"] == first["id"]
    assert second["payload"] == {"value": 1}


def test_idempotency_key_cannot_cross_job_or_owner_scope():
    from jobs.types import JobDefinition

    runtime = _runtime()
    runtime.register(JobDefinition("test.one", lambda context, payload: payload))
    runtime.register(JobDefinition("test.two", lambda context, payload: payload))
    runtime.enqueue(
        "test.one", {}, idempotency_key="shared-key", owner_id="owner-1"
    )

    with pytest.raises(ValueError, match="different job scope"):
        runtime.enqueue(
            "test.two", {}, idempotency_key="shared-key", owner_id="owner-1"
        )
    with pytest.raises(ValueError, match="different job scope"):
        runtime.enqueue(
            "test.one", {}, idempotency_key="shared-key", owner_id="owner-2"
        )


def test_retry_safe_job_stops_after_bounded_attempts():
    from jobs.types import JobDefinition

    runtime = _runtime(default_max_attempts=2)

    def fail(_context, _payload):
        raise RuntimeError("sensitive internal detail")

    runtime.register(JobDefinition("test.retry", fail, retry_safe=True))
    job, _ = runtime.enqueue("test.retry", {})

    assert runtime.run_once() is True
    assert runtime.get_job(job["id"])["status"] == "queued"
    assert runtime.run_once() is True
    failed = runtime.get_job(job["id"])
    assert failed["status"] == "failed"
    assert failed["attempt_count"] == 2
    assert failed["error_type"] == "RuntimeError"
    assert "sensitive internal detail" not in str(failed)


def test_non_retry_safe_job_fails_once_and_queued_job_can_cancel():
    from jobs.types import JobDefinition

    runtime = _runtime(default_max_attempts=3)
    runtime.register(JobDefinition(
        "test.unsafe", lambda context, payload: 1 / 0, retry_safe=False
    ))
    failed_job, _ = runtime.enqueue("test.unsafe", {})
    runtime.run_once()
    assert runtime.get_job(failed_job["id"])["status"] == "failed"
    assert runtime.get_job(failed_job["id"])["attempt_count"] == 1

    runtime.register(JobDefinition("test.cancel", lambda context, payload: {}))
    cancelled_job, _ = runtime.enqueue("test.cancel", {})
    assert runtime.cancel_job(cancelled_job["id"]) is True
    assert runtime.get_job(cancelled_job["id"])["status"] == "cancelled"


def test_cooperative_running_cancellation_prevents_success():
    from jobs.types import JobDefinition

    repository = FakeJobRepository()
    runtime = _runtime(repository)

    def handler(context, _payload):
        repository.request_cancel(context.job_id)
        context.check_cancelled()

    runtime.register(JobDefinition("test.cooperative", handler))
    job, _ = runtime.enqueue("test.cooperative", {})
    runtime.run_once()
    assert runtime.get_job(job["id"])["status"] == "cancelled"


def test_job_waits_for_explicit_approval_then_resumes():
    from jobs.types import JobDefinition

    runtime = _runtime()

    def handler(context, _payload):
        context.require_approval({"action": "publish", "token": "secret"})
        return {"published": True}

    runtime.register(JobDefinition("test.approval", handler))
    job, _ = runtime.enqueue("test.approval", {})

    runtime.run_once()
    waiting = runtime.get_job(job["id"])
    assert waiting["status"] == "waiting_approval"
    assert waiting["approval_request"]["token"] == "[REDACTED]"
    assert runtime.resolve_job_approval(job["id"], True) is True
    runtime.run_once()
    assert runtime.get_job(job["id"])["status"] == "succeeded"


def test_approval_pause_does_not_consume_retry_attempt():
    from jobs.types import JobDefinition

    runtime = _runtime()
    runtime.register(JobDefinition(
        "test.limit",
        lambda context, payload: (
            context.require_approval({"action": "retry"})
            and {"approved": True}
        ),
        max_attempts=1,
    ))
    job, _ = runtime.enqueue("test.limit", {})
    runtime.run_once()

    assert runtime.get_job(job["id"])["attempt_count"] == 0
    assert runtime.resolve_job_approval(job["id"], True) is True
    runtime.run_once()
    completed = runtime.get_job(job["id"])
    assert completed["status"] == "succeeded"
    assert completed["attempt_count"] == 1


def test_approval_resolution_cannot_override_exhausted_state():
    from jobs.types import JobDefinition

    repository = FakeJobRepository()
    runtime = _runtime(repository)
    runtime.register(JobDefinition("test.exhausted", lambda context, payload: {}))
    job, _ = runtime.enqueue("test.exhausted", {})
    stored = repository.jobs[job["id"]]
    stored.status = "waiting_approval"
    stored.attempt_count = stored.max_attempts

    assert runtime.resolve_job_approval(job["id"], True) is True
    exhausted = runtime.get_job(job["id"])
    assert exhausted["status"] == "failed"
    assert exhausted["error_type"] == "JobAttemptLimitExceeded"


def test_runtime_recovery_distinguishes_retry_safe_handlers():
    from jobs.types import JobDefinition

    repository = Mock()
    repository.recover_interrupted.return_value = {
        "requeued": 0, "waiting_approval": 0, "cancelled": 0, "failed": 0
    }
    repository.claim_next.return_value = None
    runtime = _runtime(repository)
    runtime.register(JobDefinition("test.safe", Mock(), retry_safe=True))
    runtime.register(JobDefinition("test.unsafe", Mock(), retry_safe=False))

    assert runtime.start() is True
    runtime.close(wait=True)

    repository.recover_interrupted.assert_called_once_with({"test.safe"})
    assert runtime.running is False


def test_runtime_rejects_unregistered_invalid_and_oversized_payloads():
    from jobs.types import JobDefinition

    runtime = _runtime(payload_max_chars=30)
    runtime.register(JobDefinition("test.valid", lambda context, payload: {}))

    with pytest.raises(ValueError, match="unregistered"):
        runtime.enqueue("test.unknown", {})
    with pytest.raises(ValueError, match="JSON object"):
        runtime.enqueue("test.valid", ["not", "an", "object"])
    with pytest.raises(ValueError, match="character limit"):
        runtime.enqueue("test.valid", {"value": "x" * 100})


def test_validator_output_is_resanitized_and_delay_must_be_timezone_aware():
    from datetime import datetime
    from jobs.types import JobDefinition

    def validator(payload):
        payload["token"] = "validator-secret"

    runtime = _runtime()
    runtime.register(JobDefinition(
        "test.validator", lambda context, payload: {}, validator=validator
    ))

    job, _ = runtime.enqueue("test.validator", {})
    assert job["payload"]["token"] == "[REDACTED]"
    with pytest.raises(ValueError, match="timezone-aware"):
        runtime.enqueue("test.validator", {}, available_at=datetime.now())


def test_aika_service_delegates_jobs_and_closes_runtime():
    from application.service import AikaService

    brain = SimpleNamespace(
        current_agent_id="aika",
        current_session=SimpleNamespace(id="session-1"),
        tool_manager=None,
        llm=SimpleNamespace(model="test-model"),
        close=Mock(),
    )
    job_runtime = Mock()
    job_runtime.running = True
    job_runtime.enqueue.return_value = ({"id": "job-1"}, True)
    service = AikaService(brain=brain, job_runtime=job_runtime)

    result = service.enqueue_job("test.echo", {"value": 1}, owner_id="user-1")

    assert result == ({"id": "job-1"}, True)
    job_runtime.enqueue.assert_called_once_with(
        "test.echo",
        {"value": 1},
        owner_id="user-1",
        agent_id="aika",
        session_id="session-1",
    )
    assert service.get_status()["job_worker_running"] is True
    service.close(wait=True)
    job_runtime.close.assert_called_once_with(wait=True)
    brain.close.assert_called_once_with(wait=True)
