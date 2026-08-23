from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class ReminderTool(BaseTool):
    description = (
        "Creates, lists, reschedules, cancels, and acknowledges durable reminders. "
        "Use ISO-8601 datetimes; include an offset when the user provides one."
    )
    category = ToolCategory.PRODUCTIVITY
    permission = ToolPermission.MEDIUM

    def __init__(self, service):
        self.service = service

    @property
    def name(self):
        return "reminder"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "action": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "One of create, list, due, acknowledge, cancel, reschedule"
                    ),
                },
                "message": {
                    "type": "string",
                    "required": False,
                    "description": "Reminder message for create",
                },
                "scheduled_for": {
                    "type": "string",
                    "required": False,
                    "description": "ISO-8601 datetime for create or reschedule",
                },
                "timezone": {
                    "type": "string",
                    "required": False,
                    "description": "IANA timezone such as Asia/Manila",
                },
                "recurrence_kind": {
                    "type": "string",
                    "required": False,
                    "description": "Optional: none, interval, daily, or weekly",
                },
                "interval_seconds": {
                    "type": "integer",
                    "required": False,
                    "description": "Interval duration in seconds",
                },
                "time": {
                    "type": "string",
                    "required": False,
                    "description": "Local HH:MM time for daily or weekly recurrence",
                },
                "weekday": {
                    "type": "integer",
                    "required": False,
                    "description": "Weekly recurrence weekday, Monday=0 through Sunday=6",
                },
                "reminder_id": {
                    "type": "string",
                    "required": False,
                    "description": "Reminder ID for cancel or reschedule",
                },
                "occurrence_id": {
                    "type": "string",
                    "required": False,
                    "description": "Due occurrence ID for acknowledgement",
                },
            },
        }

    @staticmethod
    def _recurrence(kind, interval_seconds=None, clock=None, weekday=None):
        if kind is None:
            return None, False
        kind = str(kind).strip().lower()
        if kind in {"", "none", "one-time", "one_time"}:
            return None, True
        if kind == "interval":
            return {
                "kind": "interval",
                "seconds": interval_seconds,
            }, True
        if kind == "daily":
            return {"kind": "daily", "time": clock}, True
        if kind == "weekly":
            return {
                "kind": "weekly",
                "weekday": weekday,
                "time": clock,
            }, True
        raise ValueError("Unsupported reminder recurrence kind")

    def execute(
        self,
        action,
        message=None,
        scheduled_for=None,
        timezone=None,
        recurrence_kind=None,
        interval_seconds=None,
        time=None,
        weekday=None,
        reminder_id=None,
        occurrence_id=None,
    ):
        action = str(action).strip().lower()
        try:
            recurrence, recurrence_supplied = self._recurrence(
                recurrence_kind,
                interval_seconds=interval_seconds,
                clock=time,
                weekday=weekday,
            )
            if action == "create":
                if message is None or scheduled_for is None:
                    raise ValueError(
                        "create requires message and scheduled_for"
                    )
                reminder, created = self.service.create_reminder(
                    message,
                    scheduled_for,
                    timezone_name=timezone,
                    recurrence=recurrence,
                )
                return {
                    "success": True,
                    "created": created,
                    "reminder": reminder,
                }
            if action == "list":
                return {
                    "success": True,
                    "reminders": self.service.get_reminders(limit=100),
                }
            if action == "due":
                return {
                    "success": True,
                    "reminders": self.service.get_due_reminders(limit=100),
                }
            if action == "acknowledge":
                if not occurrence_id:
                    raise ValueError(
                        "acknowledge requires occurrence_id"
                    )
                return {
                    "success": self.service.acknowledge_reminder(
                        occurrence_id
                    )
                }
            if action == "cancel":
                if not reminder_id:
                    raise ValueError("cancel requires reminder_id")
                return {
                    "success": self.service.cancel_reminder(reminder_id)
                }
            if action == "reschedule":
                if not reminder_id or scheduled_for is None:
                    raise ValueError(
                        "reschedule requires reminder_id and scheduled_for"
                    )
                options = {"timezone_name": timezone}
                if recurrence_supplied:
                    options["recurrence"] = recurrence
                reminder = self.service.reschedule_reminder(
                    reminder_id,
                    scheduled_for,
                    **options,
                )
                return {
                    "success": reminder is not None,
                    "reminder": reminder,
                }
            raise ValueError("Unsupported reminder action")
        except ValueError as exc:
            return {"success": False, "error": str(exc)}
