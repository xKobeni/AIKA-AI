import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from database.db import db_session
from database.models import Reminder, ReminderOccurrence
from reminders.types import ReminderStatus


def _utcnow():
    return datetime.now(timezone.utc)


def _same_instant(first, second):
    if first is None or second is None:
        return first is second
    return first.astimezone(timezone.utc) == second.astimezone(timezone.utc)


class ReminderRepository:
    """Transactional reminder schedules and due-occurrence outbox."""

    def create(
        self,
        message,
        timezone_name,
        scheduled_for,
        recurrence,
        *,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
    ):
        if idempotency_key:
            with db_session() as db:
                existing = (
                    db.query(Reminder)
                    .filter(Reminder.idempotency_key == idempotency_key)
                    .first()
                )
                if existing is not None:
                    return existing, False

        now = _utcnow()
        reminder = Reminder(
            id=uuid.uuid4().hex,
            message=message,
            timezone=timezone_name,
            recurrence=recurrence,
            status=ReminderStatus.ACTIVE.value,
            revision=1,
            trigger_count=0,
            next_run_at=scheduled_for,
            owner_id=owner_id,
            agent_id=agent_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            created_at=now,
            updated_at=now,
        )
        try:
            with db_session() as db:
                db.add(reminder)
                db.flush()
                db.refresh(reminder)
                return reminder, True
        except IntegrityError:
            if not idempotency_key:
                raise
            with db_session() as db:
                existing = (
                    db.query(Reminder)
                    .filter(Reminder.idempotency_key == idempotency_key)
                    .first()
                )
                if existing is None:
                    raise
                return existing, False

    def get(self, reminder_id):
        with db_session() as db:
            return (
                db.query(Reminder)
                .filter(Reminder.id == reminder_id)
                .first()
            )

    def list_reminders(
        self,
        *,
        status=None,
        owner_id=None,
        agent_id=None,
        limit=100,
    ):
        limit = max(1, min(int(limit), 500))
        with db_session() as db:
            query = db.query(Reminder)
            if status is not None:
                query = query.filter(Reminder.status == status)
            if owner_id is not None:
                query = query.filter(Reminder.owner_id == owner_id)
            if agent_id is not None:
                query = query.filter(Reminder.agent_id == agent_id)
            return (
                query.order_by(Reminder.created_at.desc())
                .limit(limit)
                .all()
            )

    def list_active(self, limit=1000):
        limit = max(1, min(int(limit), 5000))
        with db_session() as db:
            return (
                db.query(Reminder)
                .filter(
                    Reminder.status == ReminderStatus.ACTIVE.value,
                    Reminder.next_run_at.isnot(None),
                )
                .order_by(Reminder.next_run_at.asc())
                .limit(limit)
                .all()
            )

    def list_due_occurrences(
        self,
        *,
        owner_id=None,
        agent_id=None,
        limit=100,
    ):
        limit = max(1, min(int(limit), 500))
        with db_session() as db:
            query = (
                db.query(ReminderOccurrence, Reminder)
                .join(Reminder, Reminder.id == ReminderOccurrence.reminder_id)
                .filter(ReminderOccurrence.acknowledged_at.is_(None))
            )
            if owner_id is not None:
                query = query.filter(Reminder.owner_id == owner_id)
            if agent_id is not None:
                query = query.filter(Reminder.agent_id == agent_id)
            return (
                query.order_by(ReminderOccurrence.scheduled_for.asc())
                .limit(limit)
                .all()
            )

    def set_next_job(self, reminder_id, revision, scheduled_for, job_id):
        now = _utcnow()
        with db_session() as db:
            reminder = (
                db.query(Reminder)
                .filter(Reminder.id == reminder_id)
                .with_for_update()
                .first()
            )
            if (
                reminder is None
                or reminder.status != ReminderStatus.ACTIVE.value
                or reminder.revision != revision
                or not _same_instant(reminder.next_run_at, scheduled_for)
            ):
                return False
            reminder.next_job_id = job_id
            reminder.updated_at = now
            return True

    def trigger(
        self,
        reminder_id,
        revision,
        scheduled_for,
        job_id,
        next_run_at,
    ):
        now = _utcnow()
        with db_session() as db:
            reminder = (
                db.query(Reminder)
                .filter(Reminder.id == reminder_id)
                .with_for_update()
                .first()
            )
            if reminder is None:
                return {"action": "missing", "reminder": None, "occurrence": None}
            if reminder.status != ReminderStatus.ACTIVE.value:
                return {
                    "action": "inactive",
                    "reminder": reminder,
                    "occurrence": None,
                }
            if (
                reminder.revision != revision
                or not _same_instant(reminder.next_run_at, scheduled_for)
            ):
                return {
                    "action": "stale",
                    "reminder": reminder,
                    "occurrence": None,
                }

            occurrence = (
                db.query(ReminderOccurrence)
                .filter(
                    ReminderOccurrence.reminder_id == reminder.id,
                    ReminderOccurrence.revision == revision,
                    ReminderOccurrence.scheduled_for == scheduled_for,
                )
                .first()
            )
            created = occurrence is None
            if occurrence is None:
                occurrence = ReminderOccurrence(
                    id=uuid.uuid4().hex,
                    reminder_id=reminder.id,
                    revision=revision,
                    job_id=job_id,
                    scheduled_for=scheduled_for,
                    triggered_at=now,
                    created_at=now,
                )
                db.add(occurrence)

            reminder.trigger_count += 1 if created else 0
            reminder.last_triggered_at = now
            reminder.next_job_id = None
            reminder.updated_at = now
            if reminder.recurrence is not None and next_run_at is not None:
                reminder.next_run_at = next_run_at
            else:
                reminder.status = ReminderStatus.COMPLETED.value
                reminder.next_run_at = None

            db.flush()
            db.refresh(reminder)
            db.refresh(occurrence)
            return {
                "action": "triggered" if created else "duplicate",
                "reminder": reminder,
                "occurrence": occurrence,
            }

    def acknowledge(
        self,
        occurrence_id,
        *,
        owner_id=None,
        agent_id=None,
    ):
        now = _utcnow()
        with db_session() as db:
            occurrence = (
                db.query(ReminderOccurrence)
                .filter(ReminderOccurrence.id == occurrence_id)
                .with_for_update()
                .first()
            )
            if occurrence is None:
                return None
            reminder = (
                db.query(Reminder)
                .filter(Reminder.id == occurrence.reminder_id)
                .first()
            )
            if reminder is None:
                return None
            if owner_id is not None and reminder.owner_id != owner_id:
                return None
            if agent_id is not None and reminder.agent_id != agent_id:
                return None
            if occurrence.acknowledged_at is None:
                occurrence.acknowledged_at = now
            db.flush()
            db.refresh(occurrence)
            return occurrence

    def cancel(self, reminder_id, *, owner_id=None, agent_id=None):
        now = _utcnow()
        with db_session() as db:
            reminder = (
                db.query(Reminder)
                .filter(Reminder.id == reminder_id)
                .with_for_update()
                .first()
            )
            if reminder is None:
                return False, None
            if owner_id is not None and reminder.owner_id != owner_id:
                return False, None
            if agent_id is not None and reminder.agent_id != agent_id:
                return False, None
            if reminder.status == ReminderStatus.CANCELLED.value:
                return True, reminder.next_job_id
            if reminder.status == ReminderStatus.COMPLETED.value:
                return False, None
            job_id = reminder.next_job_id
            reminder.status = ReminderStatus.CANCELLED.value
            reminder.next_run_at = None
            reminder.next_job_id = None
            reminder.cancelled_at = now
            reminder.updated_at = now
            return True, job_id

    def reschedule(
        self,
        reminder_id,
        scheduled_for,
        recurrence,
        timezone_name,
        *,
        owner_id=None,
        agent_id=None,
    ):
        now = _utcnow()
        with db_session() as db:
            reminder = (
                db.query(Reminder)
                .filter(Reminder.id == reminder_id)
                .with_for_update()
                .first()
            )
            if reminder is None:
                return None, None
            if owner_id is not None and reminder.owner_id != owner_id:
                return None, None
            if agent_id is not None and reminder.agent_id != agent_id:
                return None, None
            if reminder.status == ReminderStatus.CANCELLED.value:
                return None, None
            old_job_id = reminder.next_job_id
            reminder.status = ReminderStatus.ACTIVE.value
            reminder.revision += 1
            reminder.recurrence = recurrence
            reminder.timezone = timezone_name
            reminder.next_run_at = scheduled_for
            reminder.next_job_id = None
            reminder.cancelled_at = None
            reminder.updated_at = now
            db.flush()
            db.refresh(reminder)
            return reminder, old_job_id
