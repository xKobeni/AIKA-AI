from datetime import datetime

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class DateTimeTool(BaseTool):
    """Return the host operating system's local date and time."""

    description = "Returns the current local date and time from the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.LOW
    response_policy = "direct_result"

    def __init__(self, clock=None):
        self._clock = clock

    @property
    def name(self):
        return "date_time"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {},
        }

    def execute(self):
        now = self._clock() if self._clock is not None else datetime.now().astimezone()
        if now.tzinfo is None:
            now = now.astimezone()

        timezone_name = now.tzname() or "local time"
        utc_offset = now.strftime("%z")
        if utc_offset:
            utc_offset = f"UTC{utc_offset[:3]}:{utc_offset[3:]}"

        date_text = now.strftime("%A, %B %d, %Y")
        time_text = now.strftime("%I:%M:%S %p").lstrip("0")
        zone_text = ", ".join(
            part for part in (timezone_name, utc_offset) if part
        )
        text = f"Today is {date_text}. The local time is {time_text}"
        if zone_text:
            text += f" ({zone_text})"
        text += "."

        return {
            "success": True,
            "text": text,
            "date": now.date().isoformat(),
            "time": now.time().isoformat(timespec="seconds"),
            "timezone": timezone_name,
            "utc_offset": utc_offset,
            "iso": now.isoformat(timespec="seconds"),
        }
