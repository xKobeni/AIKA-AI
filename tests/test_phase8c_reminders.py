from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest


def _reminder(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4().hex,
        "message": "Stand up",
        "timezone": "Asia/Manila",
        "recurrence": None,
        "status": "active",
        "revision": 1,
        "trigger_count": 0,
        "next_run_at": now + timedelta(minutes=5),
        "next_job_id": None,
        "owner_id": "owner-1",
        "agent_id": "aika",
        "session_id": "session-1",
        "idempotency_key": None,
        "last_triggered_at": None,
        "created_at": now,
        "updated_at": now,
        "cancelled_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class FakeJobRuntime:
    def __init__(self):
        self.definitions = {}
        self.jobs = {}
        self.cancelled = []

    def register(self, definition):
        self.definitions[definition.name] = definition

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
        for job in self.jobs.values():
            if job["idempotency_key"] == idempotency_key:
                return job, False
        job = {
            "id": uuid.uuid4().hex,
            "type": job_type,
            "payload": payload,
            "status": "queued",
            "owner_id": owner_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
            "available_at": available_at.isoformat(),
        }
        self.jobs[job["id"]] = job
        return job, True

    def cancel_job(self, job_id):
        self.cancelled.append(job_id)
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "cancelled"
        return True


def test_reminder_models_and_migration_define_durable_occurrences():
    from database.migrations import MIGRATIONS
    from database.models import Reminder, ReminderOccurrence

    reminder_constraints = {
        constraint.name for constraint in Reminder.__table__.constraints
    }
    occurrence_constraints = {
        constraint.name
        for constraint in ReminderOccurrence.__table__.constraints
    }
    reminder_fk = next(iter(Reminder.__table__.c.next_job_id.foreign_keys))
    occurrence_fk = next(
        iter(ReminderOccurrence.__table__.c.reminder_id.foreign_keys)
    )

    assert "uq_reminders_idempotency_key" in reminder_constraints
    assert "uq_reminder_occurrence_schedule" in occurrence_constraints
    assert reminder_fk.target_fullname == "jobs.id"
    assert reminder_fk.ondelete == "SET NULL"
    assert occurrence_fk.target_fullname == "reminders.id"
    assert occurrence_fk.ondelete == "CASCADE"
    migration = next(
        migration for migration in MIGRATIONS if migration.version == 4
    )
    assert migration.name == "durable reminders and occurrences"


def test_schedule_time_supports_named_timezone_and_rejects_unknown_zone():
    from reminders.recurrence import normalize_schedule_time

    scheduled = normalize_schedule_time("2026-08-23T18:00:00", "Asia/Manila")

    assert scheduled == datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError, match="unknown timezone"):
        normalize_schedule_time("2026-08-23T18:00:00", "Mars/Olympus")


def test_utc_timezone_does_not_require_an_external_timezone_database(monkeypatch):
    import reminders.recurrence as recurrence

    monkeypatch.setattr(
        recurrence,
        "ZoneInfo",
        Mock(side_effect=recurrence.ZoneInfoNotFoundError("missing tzdata")),
    )

    name, zone = recurrence.get_timezone("UTC")

    assert name == "UTC"
    assert zone is timezone.utc


def test_interval_recurrence_skips_missed_intervals_without_flooding():
    from reminders.recurrence import next_occurrence

    scheduled = datetime(2026, 8, 23, 0, 0, tzinfo=timezone.utc)
    now = scheduled + timedelta(minutes=5, seconds=30)

    result = next_occurrence(
        scheduled,
        {"kind": "interval", "seconds": 60},
        "UTC",
        now=now,
    )

    assert result == scheduled + timedelta(minutes=6)


def test_daily_and_weekly_recurrence_preserve_local_wall_time():
    from reminders.recurrence import next_occurrence

    scheduled = datetime(2026, 8, 23, 10, 0, tzinfo=timezone.utc)
    daily = next_occurrence(
        scheduled,
        {"kind": "daily", "time": "18:00"},
        "Asia/Manila",
        now=scheduled,
    )
    weekly = next_occurrence(
        scheduled,
        {"kind": "weekly", "weekday": 0, "time": "09:30"},
        "Asia/Manila",
        now=scheduled,
    )

    assert daily == datetime(2026, 8, 24, 10, 0, tzinfo=timezone.utc)
    assert weekly == datetime(2026, 8, 24, 1, 30, tzinfo=timezone.utc)


def test_recurrence_validation_enforces_supported_bounded_shapes():
    from reminders.recurrence import normalize_recurrence

    assert normalize_recurrence(
        {"kind": "interval", "seconds": 60}, min_interval_seconds=60
    ) == {"kind": "interval", "seconds": 60}
    with pytest.raises(ValueError, match="at least 60"):
        normalize_recurrence(
            {"kind": "interval", "seconds": 10}, min_interval_seconds=60
        )
    with pytest.raises(ValueError, match="weekday"):
        normalize_recurrence(
            {"kind": "weekly", "weekday": 7, "time": "09:00"}
        )
    with pytest.raises(ValueError, match="kind"):
        normalize_recurrence({"kind": "cron", "value": "* * * * *"})


def test_scheduler_registers_handler_and_reconciles_active_reminders():
    from reminders.scheduler import REMINDER_JOB_TYPE, ReminderScheduler

    job_runtime = FakeJobRuntime()
    repository = Mock()
    reminder = _reminder()
    repository.list_active.return_value = [reminder]
    repository.set_next_job.return_value = True
    scheduler = ReminderScheduler(
        job_runtime,
        repository,
        min_interval_seconds=60,
    )

    assert scheduler.start() is True

    assert REMINDER_JOB_TYPE in job_runtime.definitions
    repository.list_active.assert_called_once_with(1000)
    repository.set_next_job.assert_called_once()
    job = next(iter(job_runtime.jobs.values()))
    assert job["available_at"] == reminder.next_run_at.isoformat()
    assert job["payload"]["reminder_id"] == reminder.id


def test_create_reminder_validates_redacts_and_schedules_job():
    from reminders.scheduler import ReminderScheduler

    job_runtime = FakeJobRuntime()
    repository = Mock()
    repository.list_active.return_value = []
    repository.set_next_job.return_value = True
    created_reminder = _reminder(message="token=[REDACTED]")
    repository.create.return_value = (created_reminder, True)
    scheduler = ReminderScheduler(job_runtime, repository)
    scheduler.start()

    result, created = scheduler.create_reminder(
        "token=private-value",
        created_reminder.next_run_at,
        timezone_name="Asia/Manila",
        owner_id="owner-1",
        agent_id="aika",
    )

    assert created is True
    assert result["id"] == created_reminder.id
    persisted_message = repository.create.call_args.args[0]
    assert persisted_message == "token=[REDACTED]"
    assert len(job_runtime.jobs) == 1


def test_delivery_creates_occurrence_and_schedules_next_recurrence():
    from reminders.scheduler import ReminderScheduler

    job_runtime = FakeJobRuntime()
    repository = Mock()
    scheduled = datetime.now(timezone.utc) - timedelta(minutes=5)
    reminder = _reminder(
        recurrence={"kind": "interval", "seconds": 60},
        next_run_at=scheduled,
    )
    next_reminder = _reminder(
        id=reminder.id,
        recurrence=reminder.recurrence,
        next_run_at=datetime.now(timezone.utc) + timedelta(seconds=30),
    )
    occurrence = SimpleNamespace(
        id=uuid.uuid4().hex,
        scheduled_for=scheduled,
        triggered_at=datetime.now(timezone.utc),
        acknowledged_at=None,
    )
    repository.list_active.return_value = []
    repository.get.return_value = reminder
    repository.trigger.return_value = {
        "action": "triggered",
        "reminder": next_reminder,
        "occurrence": occurrence,
    }
    repository.set_next_job.return_value = True
    scheduler = ReminderScheduler(job_runtime, repository)
    scheduler.start()
    notification = Mock()
    scheduler.set_notification_handler(notification)
    context = SimpleNamespace(job_id=uuid.uuid4().hex, check_cancelled=Mock())

    result = scheduler._deliver(context, {
        "reminder_id": reminder.id,
        "revision": 1,
        "scheduled_for": scheduled.isoformat(),
    })

    assert result["action"] == "triggered"
    assert result["occurrence_id"] == occurrence.id
    next_run = repository.trigger.call_args.args[4]
    assert next_run > datetime.now(timezone.utc)
    assert len(job_runtime.jobs) == 1
    notification.assert_called_once()
    assert notification.call_args.args[0]["occurrence_id"] == occurrence.id


def test_cancel_and_reschedule_control_the_linked_job():
    from reminders.scheduler import ReminderScheduler

    job_runtime = FakeJobRuntime()
    repository = Mock()
    repository.list_active.return_value = []
    repository.set_next_job.return_value = True
    scheduler = ReminderScheduler(job_runtime, repository)
    scheduler.start()

    repository.cancel.return_value = (True, "old-job")
    assert scheduler.cancel_reminder("reminder-1", agent_id="aika") is True
    assert "old-job" in job_runtime.cancelled

    changed = _reminder(revision=2)
    repository.get.return_value = changed
    repository.reschedule.return_value = (changed, "older-job")
    result = scheduler.reschedule_reminder(
        changed.id,
        changed.next_run_at,
        timezone_name="Asia/Manila",
        recurrence={"kind": "daily", "time": "18:00"},
        agent_id="aika",
    )

    assert result["revision"] == 2
    assert "older-job" in job_runtime.cancelled
    assert len(job_runtime.jobs) == 1


def test_reschedule_preserves_recurrence_when_not_explicitly_replaced():
    from reminders.scheduler import ReminderScheduler

    job_runtime = FakeJobRuntime()
    repository = Mock()
    repository.list_active.return_value = []
    repository.set_next_job.return_value = True
    existing = _reminder(recurrence={"kind": "interval", "seconds": 300})
    changed = _reminder(
        id=existing.id,
        recurrence=existing.recurrence,
        revision=2,
    )
    repository.get.return_value = existing
    repository.reschedule.return_value = (changed, None)
    scheduler = ReminderScheduler(job_runtime, repository)
    scheduler.start()

    scheduler.reschedule_reminder(existing.id, changed.next_run_at)

    assert repository.reschedule.call_args.args[2] == existing.recurrence


def test_due_occurrences_are_scoped_and_acknowledged():
    from reminders.scheduler import ReminderScheduler

    job_runtime = FakeJobRuntime()
    repository = Mock()
    repository.list_active.return_value = []
    reminder = _reminder()
    occurrence = SimpleNamespace(
        id=uuid.uuid4().hex,
        scheduled_for=reminder.next_run_at,
        triggered_at=datetime.now(timezone.utc),
        acknowledged_at=None,
    )
    repository.list_due_occurrences.return_value = [(occurrence, reminder)]
    repository.acknowledge.return_value = occurrence
    scheduler = ReminderScheduler(job_runtime, repository)
    scheduler.start()

    due = scheduler.get_due_reminders(agent_id="aika")
    acknowledged = scheduler.acknowledge_reminder(
        occurrence.id, agent_id="aika"
    )

    assert due[0]["message"] == "Stand up"
    assert due[0]["occurrence_id"] == occurrence.id
    assert acknowledged is True
    repository.list_due_occurrences.assert_called_once_with(agent_id="aika")


def test_application_service_scopes_reminder_operations_to_current_agent():
    from application.service import AikaService

    brain = SimpleNamespace(
        current_agent_id="aika",
        current_session=SimpleNamespace(id="session-1"),
        tool_manager=None,
        llm=SimpleNamespace(model="test-model"),
        close=Mock(),
    )
    scheduler = Mock()
    scheduler.create_reminder.return_value = ({"id": "reminder-1"}, True)
    service = AikaService(brain=brain, reminder_scheduler=scheduler)

    result = service.create_reminder("message", "2026-08-24T10:00:00Z")
    service.get_due_reminders(limit=20)
    service.acknowledge_reminder("occurrence-1")
    service.cancel_reminder("reminder-1")

    assert result == ({"id": "reminder-1"}, True)
    scheduler.create_reminder.assert_called_once_with(
        "message",
        "2026-08-24T10:00:00Z",
        agent_id="aika",
        session_id="session-1",
    )
    scheduler.get_due_reminders.assert_called_once_with(
        owner_id=None, agent_id="aika", limit=20
    )
    scheduler.acknowledge_reminder.assert_called_once_with(
        "occurrence-1", owner_id=None, agent_id="aika"
    )
    scheduler.cancel_reminder.assert_called_once_with(
        "reminder-1", owner_id=None, agent_id="aika"
    )


def test_application_service_registers_reminder_tool_with_brain_tool_manager():
    from application.service import AikaService

    tool_manager = Mock()
    brain = SimpleNamespace(
        current_agent_id="aika",
        current_session=SimpleNamespace(id="session-1"),
        tool_manager=tool_manager,
        llm=SimpleNamespace(model="test-model"),
        close=Mock(),
    )

    AikaService(brain=brain, reminder_scheduler=Mock())

    registered_tool = tool_manager.register_tool.call_args.args[0]
    assert registered_tool.name == "reminder"
    assert registered_tool.service.brain is brain


def test_reminder_tool_exposes_scheduler_to_normal_tool_calling():
    from tools.reminder_tool import ReminderTool

    service = Mock()
    service.create_reminder.return_value = ({"id": "reminder-1"}, True)
    service.reschedule_reminder.return_value = {"id": "reminder-1"}
    tool = ReminderTool(service)

    created = tool.execute(
        action="create",
        message="Stand up",
        scheduled_for="2026-08-24T10:00:00+08:00",
        timezone="Asia/Manila",
        recurrence_kind="daily",
        time="10:00",
    )
    rescheduled = tool.execute(
        action="reschedule",
        reminder_id="reminder-1",
        scheduled_for="2026-08-25T10:00:00+08:00",
    )

    assert created["success"] is True
    service.create_reminder.assert_called_once_with(
        "Stand up",
        "2026-08-24T10:00:00+08:00",
        timezone_name="Asia/Manila",
        recurrence={"kind": "daily", "time": "10:00"},
    )
    assert rescheduled["success"] is True
    service.reschedule_reminder.assert_called_once_with(
        "reminder-1",
        "2026-08-25T10:00:00+08:00",
        timezone_name=None,
    )
    assert tool.get_native_schema()["function"]["name"] == "reminder"


def test_reminder_tool_rejects_incomplete_or_unknown_actions():
    from tools.reminder_tool import ReminderTool

    tool = ReminderTool(Mock())

    assert tool.execute(action="create")["success"] is False
    assert tool.execute(action="delete-everything")["success"] is False


def test_reminder_timezone_setting_rejects_unknown_zone():
    from handlers.config_handler import ConfigHandler

    error = ConfigHandler()._validate_value(
        "reminder_default_timezone", "Mars/Olympus"
    )

    assert "unknown timezone" in error


def test_cli_reminder_commands_use_explicit_bounded_syntax():
    from reminders.commands import handle_reminder_command

    service = Mock()
    service.create_reminder.return_value = ({"id": "reminder-1"}, True)
    service.get_reminders.return_value = []
    output = Mock()

    assert handle_reminder_command(
        service,
        "remind 2026-08-24T10:00:00+08:00 | drink water",
        output,
    ) is True
    service.create_reminder.assert_called_with(
        "drink water", "2026-08-24T10:00:00+08:00"
    )

    assert handle_reminder_command(
        service,
        "remind every 15m starting 2026-08-24T10:00:00Z | stretch",
        output,
    ) is True
    service.create_reminder.assert_called_with(
        "stretch",
        "2026-08-24T10:00:00Z",
        recurrence={"kind": "interval", "seconds": 900},
    )
    assert handle_reminder_command(service, "ordinary chat", output) is False
