import logging
import re
import uuid
from datetime import datetime, timezone

from config.settings import settings
from jobs.types import JobDefinition
from reminders.recurrence import (
    get_timezone,
    next_occurrence,
    normalize_recurrence,
    normalize_schedule_time,
)
from reminders.types import ReminderStatus
from repositories.reminder_repository import ReminderRepository
from security.redaction import redact_sensitive


REMINDER_JOB_TYPE = "reminder.deliver"
_HEX_ID = re.compile(r"^[0-9a-f]{32}$")
_TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled"}
_UNSET = object()
logger = logging.getLogger(__name__)


def _bounded_identifier(value, label, maximum):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value


def _parse_job_datetime(value):
    if not isinstance(value, str):
        raise ValueError("scheduled_for must be an ISO-8601 string")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError("scheduled_for must be an ISO-8601 string") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scheduled_for must include a timezone offset")
    return parsed.astimezone(timezone.utc)


def validate_reminder_job_payload(payload):
    reminder_id = payload.get("reminder_id")
    revision = payload.get("revision")
    scheduled_for = payload.get("scheduled_for")
    if not isinstance(reminder_id, str) or not _HEX_ID.fullmatch(reminder_id):
        raise ValueError("reminder_id must be a 32-character lowercase hex ID")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        raise ValueError("revision must be a positive integer")
    parsed = _parse_job_datetime(scheduled_for)
    return {
        "reminder_id": reminder_id,
        "revision": revision,
        "scheduled_for": parsed.isoformat(),
    }


class ReminderScheduler:
    """Durable reminders implemented as reconciled delayed jobs."""

    def __init__(
        self,
        job_runtime,
        repository=None,
        *,
        default_timezone=None,
        message_max_chars=None,
        min_interval_seconds=None,
        reconcile_limit=None,
    ):
        self.job_runtime = job_runtime
        self.repository = repository or ReminderRepository()
        self.default_timezone = (
            default_timezone or settings.reminder_default_timezone
        )
        self.message_max_chars = int(
            message_max_chars
            if message_max_chars is not None
            else settings.reminder_message_max_chars
        )
        self.min_interval_seconds = int(
            min_interval_seconds
            if min_interval_seconds is not None
            else settings.reminder_min_interval_seconds
        )
        self.reconcile_limit = int(
            reconcile_limit
            if reconcile_limit is not None
            else settings.reminder_reconcile_limit
        )
        get_timezone(self.default_timezone)
        if (
            self.message_max_chars <= 0
            or self.min_interval_seconds <= 0
            or self.reconcile_limit <= 0
        ):
            raise ValueError("reminder limits must be positive")
        self._started = False
        self._notification_handler = None

    def set_notification_handler(self, handler):
        if handler is not None and not callable(handler):
            raise TypeError("reminder notification handler must be callable")
        self._notification_handler = handler

    def _notify(self, occurrence, reminder):
        if self._notification_handler is None:
            return
        try:
            self._notification_handler(
                self._occurrence_to_dict(occurrence, reminder)
            )
        except Exception as exc:
            logger.warning(
                "Reminder notification handler failed: %s",
                type(exc).__name__,
            )

    def start(self):
        if self._started:
            return False
        self.job_runtime.register(JobDefinition(
            REMINDER_JOB_TYPE,
            self._deliver,
            validator=validate_reminder_job_payload,
            retry_safe=True,
            max_attempts=3,
        ))
        self._started = True
        self.reconcile()
        return True

    def _job_payload(self, reminder):
        return {
            "reminder_id": reminder.id,
            "revision": reminder.revision,
            "scheduled_for": reminder.next_run_at.astimezone(
                timezone.utc
            ).isoformat(),
        }

    @staticmethod
    def _job_key(reminder, repair=None):
        scheduled = reminder.next_run_at.astimezone(timezone.utc).isoformat()
        base = f"reminder:{reminder.id}:{reminder.revision}:{scheduled}"
        return f"{base}:repair:{repair}" if repair else base

    def _ensure_job(self, reminder):
        if (
            reminder is None
            or reminder.status != ReminderStatus.ACTIVE.value
            or reminder.next_run_at is None
        ):
            return None
        job, created = self.job_runtime.enqueue(
            REMINDER_JOB_TYPE,
            self._job_payload(reminder),
            owner_id=reminder.owner_id,
            agent_id=reminder.agent_id,
            session_id=reminder.session_id,
            idempotency_key=self._job_key(reminder),
            available_at=reminder.next_run_at,
        )
        if not created and job["status"] in _TERMINAL_JOB_STATUSES:
            job, created = self.job_runtime.enqueue(
                REMINDER_JOB_TYPE,
                self._job_payload(reminder),
                owner_id=reminder.owner_id,
                agent_id=reminder.agent_id,
                session_id=reminder.session_id,
                idempotency_key=self._job_key(reminder, uuid.uuid4().hex[:12]),
                available_at=reminder.next_run_at,
            )
        linked = self.repository.set_next_job(
            reminder.id,
            reminder.revision,
            reminder.next_run_at,
            job["id"],
        )
        if not linked and created:
            self.job_runtime.cancel_job(job["id"])
            return None
        return job

    def _deliver(self, context, payload):
        context.check_cancelled()
        reminder_id = payload["reminder_id"]
        revision = payload["revision"]
        scheduled_for = _parse_job_datetime(payload["scheduled_for"])
        reminder = self.repository.get(reminder_id)
        if reminder is None:
            return {"action": "missing", "reminder_id": reminder_id}

        if (
            reminder.status != ReminderStatus.ACTIVE.value
            or reminder.revision != revision
            or reminder.next_run_at is None
            or reminder.next_run_at.astimezone(timezone.utc) != scheduled_for
        ):
            self._ensure_job(reminder)
            return {"action": "stale", "reminder_id": reminder_id}

        next_run_at = next_occurrence(
            scheduled_for,
            reminder.recurrence,
            reminder.timezone,
        )
        outcome = self.repository.trigger(
            reminder_id,
            revision,
            scheduled_for,
            context.job_id,
            next_run_at,
        )
        current = outcome["reminder"]
        occurrence = outcome["occurrence"]
        if outcome["action"] == "triggered" and occurrence is not None:
            self._notify(occurrence, current)
        context.check_cancelled()
        self._ensure_job(current)
        return {
            "action": outcome["action"],
            "reminder_id": reminder_id,
            "occurrence_id": occurrence.id if occurrence is not None else None,
            "next_run_at": (
                current.next_run_at.isoformat()
                if current is not None and current.next_run_at is not None
                else None
            ),
        }

    def reconcile(self):
        checked = 0
        scheduled = 0
        for reminder in self.repository.list_active(self.reconcile_limit):
            checked += 1
            if self._ensure_job(reminder) is not None:
                scheduled += 1
        return {"checked": checked, "scheduled": scheduled}

    def create_reminder(
        self,
        message,
        scheduled_for,
        *,
        timezone_name=None,
        recurrence=None,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
    ):
        timezone_name, _ = get_timezone(
            timezone_name or self.default_timezone
        )
        message = str(message).strip() if message is not None else ""
        if not message:
            raise ValueError("reminder message must be non-empty")
        message = redact_sensitive(message)
        if len(message) > self.message_max_chars:
            raise ValueError(
                f"reminder message exceeds {self.message_max_chars} characters"
            )
        scheduled_for = normalize_schedule_time(
            scheduled_for, timezone_name
        )
        recurrence = normalize_recurrence(
            recurrence,
            min_interval_seconds=self.min_interval_seconds,
        )
        safe_owner = _bounded_identifier(owner_id, "owner_id", 100)
        safe_agent = _bounded_identifier(agent_id, "agent_id", 50)
        safe_session = _bounded_identifier(session_id, "session_id", 50)
        safe_key = _bounded_identifier(
            idempotency_key, "idempotency_key", 200
        )
        reminder, created = self.repository.create(
            message,
            timezone_name,
            scheduled_for,
            recurrence,
            owner_id=safe_owner,
            agent_id=safe_agent,
            session_id=safe_session,
            idempotency_key=safe_key,
        )
        if not created and (
            reminder.owner_id != safe_owner
            or reminder.agent_id != safe_agent
        ):
            raise ValueError(
                "idempotency key belongs to a different reminder scope"
            )
        self._ensure_job(reminder)
        return self._reminder_to_dict(reminder), created

    def get_reminder(self, reminder_id, *, owner_id=None, agent_id=None):
        reminder = self.repository.get(str(reminder_id))
        if reminder is not None and (
            (owner_id is not None and reminder.owner_id != owner_id)
            or (agent_id is not None and reminder.agent_id != agent_id)
        ):
            return None
        return self._reminder_to_dict(reminder) if reminder is not None else None

    def list_reminders(self, **filters):
        return [
            self._reminder_to_dict(reminder)
            for reminder in self.repository.list_reminders(**filters)
        ]

    def get_due_reminders(self, **filters):
        return [
            self._occurrence_to_dict(occurrence, reminder)
            for occurrence, reminder in self.repository.list_due_occurrences(
                **filters
            )
        ]

    def acknowledge_reminder(
        self, occurrence_id, *, owner_id=None, agent_id=None
    ):
        occurrence = self.repository.acknowledge(
            str(occurrence_id), owner_id=owner_id, agent_id=agent_id
        )
        return occurrence is not None

    def cancel_reminder(self, reminder_id, *, owner_id=None, agent_id=None):
        changed, job_id = self.repository.cancel(
            str(reminder_id), owner_id=owner_id, agent_id=agent_id
        )
        if changed and job_id:
            self.job_runtime.cancel_job(job_id)
        return changed

    def reschedule_reminder(
        self,
        reminder_id,
        scheduled_for,
        *,
        timezone_name=None,
        recurrence=_UNSET,
        owner_id=None,
        agent_id=None,
    ):
        existing = self.repository.get(str(reminder_id))
        if existing is None:
            return None
        timezone_name, _ = get_timezone(
            timezone_name or existing.timezone
        )
        scheduled_for = normalize_schedule_time(
            scheduled_for, timezone_name
        )
        if recurrence is _UNSET:
            recurrence = existing.recurrence
        else:
            recurrence = normalize_recurrence(
                recurrence,
                min_interval_seconds=self.min_interval_seconds,
            )
        reminder, old_job_id = self.repository.reschedule(
            str(reminder_id),
            scheduled_for,
            recurrence,
            timezone_name,
            owner_id=owner_id,
            agent_id=agent_id,
        )
        if reminder is None:
            return None
        if old_job_id:
            self.job_runtime.cancel_job(old_job_id)
        self._ensure_job(reminder)
        return self._reminder_to_dict(reminder)

    @staticmethod
    def _reminder_to_dict(reminder):
        return {
            "id": reminder.id,
            "message": reminder.message,
            "timezone": reminder.timezone,
            "recurrence": reminder.recurrence,
            "status": reminder.status,
            "revision": reminder.revision,
            "trigger_count": reminder.trigger_count,
            "next_run_at": (
                reminder.next_run_at.isoformat()
                if reminder.next_run_at is not None else None
            ),
            "owner_id": reminder.owner_id,
            "agent_id": reminder.agent_id,
            "session_id": reminder.session_id,
            "last_triggered_at": (
                reminder.last_triggered_at.isoformat()
                if reminder.last_triggered_at is not None else None
            ),
            "created_at": reminder.created_at.isoformat(),
            "updated_at": reminder.updated_at.isoformat(),
            "cancelled_at": (
                reminder.cancelled_at.isoformat()
                if reminder.cancelled_at is not None else None
            ),
        }

    @staticmethod
    def _occurrence_to_dict(occurrence, reminder):
        return {
            "occurrence_id": occurrence.id,
            "reminder_id": reminder.id,
            "message": reminder.message,
            "timezone": reminder.timezone,
            "scheduled_for": occurrence.scheduled_for.isoformat(),
            "triggered_at": occurrence.triggered_at.isoformat(),
            "acknowledged_at": (
                occurrence.acknowledged_at.isoformat()
                if occurrence.acknowledged_at is not None else None
            ),
            "owner_id": reminder.owner_id,
            "agent_id": reminder.agent_id,
        }
