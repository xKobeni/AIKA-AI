import logging
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError

from database.db import db_session
from database.models import Job, JobEvent
from jobs.types import JobStatus


logger = logging.getLogger(__name__)
TERMINAL_STATUSES = {
    JobStatus.SUCCEEDED.value,
    JobStatus.FAILED.value,
    JobStatus.CANCELLED.value,
}


def _utcnow():
    return datetime.now(timezone.utc)


class JobRepository:
    """Transactional persistence and state transitions for durable jobs."""

    @staticmethod
    def _add_event(db, job_id, event_type, data=None, now=None):
        db.add(JobEvent(
            job_id=job_id,
            event_type=event_type,
            data=data or {},
            created_at=now or _utcnow(),
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
        now = _utcnow()
        job_id = uuid.uuid4().hex
        if idempotency_key:
            with db_session() as db:
                existing = (
                    db.query(Job)
                    .filter(Job.idempotency_key == idempotency_key)
                    .first()
                )
                if existing is not None:
                    return existing, False

        try:
            with db_session() as db:
                job = Job(
                    id=job_id,
                    job_type=job_type,
                    payload=payload,
                    status=JobStatus.QUEUED.value,
                    owner_id=owner_id,
                    agent_id=agent_id,
                    session_id=session_id,
                    idempotency_key=idempotency_key,
                    progress=0,
                    attempt_count=0,
                    max_attempts=max_attempts,
                    cancel_requested=False,
                    available_at=available_at or now,
                    created_at=now,
                    updated_at=now,
                )
                db.add(job)
                self._add_event(db, job_id, "queued", now=now)
                db.flush()
                db.refresh(job)
                return job, True
        except IntegrityError:
            if not idempotency_key:
                raise
            with db_session() as db:
                existing = (
                    db.query(Job)
                    .filter(Job.idempotency_key == idempotency_key)
                    .first()
                )
                if existing is None:
                    raise
                return existing, False

    def get(self, job_id):
        with db_session() as db:
            return db.query(Job).filter(Job.id == job_id).first()

    def list_jobs(
        self,
        *,
        status=None,
        owner_id=None,
        job_type=None,
        limit=50,
    ):
        limit = max(1, min(int(limit), 200))
        with db_session() as db:
            query = db.query(Job)
            if status is not None:
                query = query.filter(Job.status == status)
            if owner_id is not None:
                query = query.filter(Job.owner_id == owner_id)
            if job_type is not None:
                query = query.filter(Job.job_type == job_type)
            return query.order_by(Job.created_at.desc()).limit(limit).all()

    def list_events(self, job_id, limit=200):
        limit = max(1, min(int(limit), 500))
        with db_session() as db:
            return (
                db.query(JobEvent)
                .filter(JobEvent.job_id == job_id)
                .order_by(JobEvent.id.asc())
                .limit(limit)
                .all()
            )

    def claim_next(self, registered_types, now=None):
        registered_types = tuple(sorted(set(registered_types)))
        if not registered_types:
            return None
        now = now or _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(
                    Job.status == JobStatus.QUEUED.value,
                    Job.available_at <= now,
                    Job.cancel_requested.is_(False),
                    Job.attempt_count < Job.max_attempts,
                    Job.job_type.in_(registered_types),
                )
                .order_by(Job.available_at.asc(), Job.created_at.asc())
                .with_for_update(skip_locked=True)
                .first()
            )
            if job is None:
                return None
            job.status = JobStatus.RUNNING.value
            job.attempt_count += 1
            job.started_at = now
            job.updated_at = now
            job.error_type = None
            self._add_event(
                db,
                job.id,
                "started",
                {"attempt": job.attempt_count},
                now,
            )
            db.flush()
            db.refresh(job)
            return job

    def update_progress(self, job_id, progress, data=None):
        progress = int(progress)
        if not 0 <= progress <= 100:
            raise ValueError("progress must be between 0 and 100")
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status != JobStatus.RUNNING.value:
                return False
            job.progress = progress
            job.updated_at = now
            event_data = {"progress": progress}
            if data:
                event_data["data"] = data
            self._add_event(db, job_id, "progress", event_data, now)
            return True

    def complete(self, job_id, result):
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status != JobStatus.RUNNING.value:
                return False
            if job.cancel_requested:
                self._mark_cancelled(db, job, now)
                return False
            job.status = JobStatus.SUCCEEDED.value
            job.result = result
            job.progress = 100
            job.updated_at = now
            job.finished_at = now
            self._add_event(db, job_id, "succeeded", now=now)
            return True

    @classmethod
    def _mark_cancelled(cls, db, job, now):
        job.status = JobStatus.CANCELLED.value
        job.cancel_requested = True
        job.updated_at = now
        job.finished_at = now
        cls._add_event(db, job.id, "cancelled", now=now)

    def mark_cancelled(self, job_id):
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status in TERMINAL_STATUSES:
                return False
            self._mark_cancelled(db, job, now)
            return True

    def fail(self, job_id, error_type, *, retryable, retry_delay_seconds):
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status != JobStatus.RUNNING.value:
                return None
            if job.cancel_requested:
                self._mark_cancelled(db, job, now)
                return JobStatus.CANCELLED.value

            job.error_type = str(error_type)[:200]
            job.updated_at = now
            if retryable and job.attempt_count < job.max_attempts:
                multiplier = 2 ** max(0, job.attempt_count - 1)
                delay = min(float(retry_delay_seconds) * multiplier, 3600.0)
                job.status = JobStatus.QUEUED.value
                job.available_at = now + timedelta(seconds=delay)
                self._add_event(
                    db,
                    job.id,
                    "retry_scheduled",
                    {"attempt": job.attempt_count, "delay_seconds": delay},
                    now,
                )
            else:
                job.status = JobStatus.FAILED.value
                job.finished_at = now
                self._add_event(
                    db,
                    job.id,
                    "failed",
                    {"error_type": job.error_type},
                    now,
                )
            return job.status

    def request_cancel(self, job_id):
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status in TERMINAL_STATUSES:
                return False
            if job.cancel_requested:
                return True
            job.cancel_requested = True
            job.updated_at = now
            if job.status in {
                JobStatus.QUEUED.value,
                JobStatus.WAITING_APPROVAL.value,
            }:
                self._mark_cancelled(db, job, now)
            else:
                self._add_event(db, job.id, "cancellation_requested", now=now)
            return True

    def is_cancel_requested(self, job_id):
        with db_session() as db:
            job = db.query(Job).filter(Job.id == job_id).first()
            return bool(
                job is None
                or job.cancel_requested
                or job.status == JobStatus.CANCELLED.value
            )

    def wait_for_approval(self, job_id, request):
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status != JobStatus.RUNNING.value:
                return False
            if job.cancel_requested:
                self._mark_cancelled(db, job, now)
                return False
            job.status = JobStatus.WAITING_APPROVAL.value
            # A cooperative approval pause is not a failed execution attempt.
            job.attempt_count = max(0, job.attempt_count - 1)
            job.approval_request = request
            job.approval_granted = None
            job.updated_at = now
            self._add_event(db, job.id, "approval_required", request, now)
            return True

    def resolve_approval(self, job_id, approved):
        now = _utcnow()
        with db_session() as db:
            job = (
                db.query(Job)
                .filter(Job.id == job_id)
                .with_for_update()
                .first()
            )
            if job is None or job.status != JobStatus.WAITING_APPROVAL.value:
                return False
            job.approval_granted = bool(approved)
            job.updated_at = now
            self._add_event(
                db,
                job.id,
                "approval_resolved",
                {"approved": bool(approved)},
                now,
            )
            if approved:
                if job.attempt_count < job.max_attempts:
                    job.status = JobStatus.QUEUED.value
                    job.available_at = now
                else:
                    job.status = JobStatus.FAILED.value
                    job.error_type = "JobAttemptLimitExceeded"
                    job.finished_at = now
                    self._add_event(
                        db,
                        job.id,
                        "failed",
                        {"error_type": job.error_type},
                        now,
                    )
            else:
                self._mark_cancelled(db, job, now)
            return True

    def recover_interrupted(self, retry_safe_types):
        retry_safe_types = set(retry_safe_types)
        now = _utcnow()
        recovered = {
            "requeued": 0,
            "waiting_approval": 0,
            "cancelled": 0,
            "failed": 0,
        }
        with db_session() as db:
            jobs = (
                db.query(Job)
                .filter(Job.status == JobStatus.RUNNING.value)
                .with_for_update(skip_locked=True)
                .all()
            )
            for job in jobs:
                job.updated_at = now
                if job.cancel_requested:
                    self._mark_cancelled(db, job, now)
                    recovered["cancelled"] += 1
                elif job.attempt_count >= job.max_attempts:
                    job.status = JobStatus.FAILED.value
                    job.error_type = "JobAttemptLimitExceeded"
                    job.finished_at = now
                    self._add_event(
                        db,
                        job.id,
                        "failed",
                        {"error_type": job.error_type},
                        now,
                    )
                    recovered["failed"] += 1
                elif (
                    job.job_type in retry_safe_types
                ):
                    job.status = JobStatus.QUEUED.value
                    job.available_at = now
                    self._add_event(db, job.id, "recovered", {"action": "requeued"}, now)
                    recovered["requeued"] += 1
                else:
                    job.status = JobStatus.WAITING_APPROVAL.value
                    job.approval_granted = None
                    job.approval_request = {
                        "reason": "interrupted_job",
                        "message": "This interrupted job requires approval before retry.",
                    }
                    self._add_event(
                        db,
                        job.id,
                        "recovered",
                        {"action": "waiting_approval"},
                        now,
                    )
                    recovered["waiting_approval"] += 1
        return recovered
