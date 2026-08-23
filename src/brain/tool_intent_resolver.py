import re

from models.tool_request import ToolRequest


class DeterministicToolIntentResolver:
    """Resolve small, high-confidence system requests without LLM guessing."""

    _DATE_TIME = re.compile(
        r"\b(?:(?:what(?:'s| is)|tell me|give me|show me)\s+"
        r"(?:the\s+)?(?:current\s+)?(?:date(?:\s+and\s+time)?|"
        r"time(?:\s+and\s+date)?)(?:\s+today)?|"
        r"what\s+(?:day|time)\s+is\s+it|today(?:'s)?\s+date|"
        r"date\s+today|time\s+now)\b",
        re.IGNORECASE,
    )
    _CAMERA = re.compile(
        r"\b(?:open|launch|start)\s+(?:my\s+|the\s+)?camera(?:\s+app)?\b",
        re.IGNORECASE,
    )
    _SCREENSHOT = re.compile(
        r"\b(?:(?:take|capture|make)\s+(?:a\s+)?"
        r"(?:screen\s*shot|screen\s+capture)|screenshot)\b",
        re.IGNORECASE,
    )
    _CAPABILITIES = re.compile(
        r"\b(?:what\s+(?:tools|capabilities)\s+(?:do\s+you\s+have|can\s+you\s+use)|"
        r"what\s+(?:tools|capabilities)\s+you\s+can\s+(?:do|use|access)|"
        r"what\s+are\s+your\s+(?:tools|capabilities)|"
        r"what\s+can\s+you\s+(?:access|do)|list\s+(?:your\s+)?(?:tools|capabilities)|"
        r"show\s+(?:me\s+)?(?:your\s+)?(?:tools|capabilities))\b",
        re.IGNORECASE,
    )

    def resolve(self, user_message):
        text = str(user_message or "").strip()
        if not text:
            return None
        if self._SCREENSHOT.search(text):
            return ToolRequest("capabilities", {"topic": "screenshot"})
        if self._CAMERA.search(text):
            return ToolRequest("app_launcher", {"app_name": "camera"})
        if self._DATE_TIME.search(text):
            return ToolRequest("date_time", {})
        if self._CAPABILITIES.search(text):
            return ToolRequest("capabilities", {})
        return None
