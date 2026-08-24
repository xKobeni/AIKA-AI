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
    _CALCULATION = re.compile(r"^[0-9+\-*/().\s]+$")
    _APPLICATION = re.compile(
        r"^(?:open|launch|start)\s+(?:the\s+)?"
        r"(?P<app>terminal|windows\s+terminal|command\s+prompt|cmd|"
        r"powershell|google\s+chrome|chrome|spotify|firefox|"
        r"visual\s+studio\s+code|vs\s+code|vscode|notepad|calculator|"
        r"file\s+explorer|explorer|control\s+panel|settings)\s*[.!?]*$",
        re.IGNORECASE,
    )
    _MEMORY_SEARCH = re.compile(
        r"\b(?:search|serach)(?:\s+through)?\s+"
        r"(?:the\s+|my\s+)?memories(?:\s+for\s+(?P<query>.+))?\s*[.!?]*$",
        re.IGNORECASE,
    )
    _WEB_SEARCH_PREFIX = re.compile(
        r"\b(?:search|serach)\s+(?:the\s+)?(?:web|internet)"
        r"(?:\s+for)?\s*(?P<query>.*)$",
        re.IGNORECASE,
    )
    _WEB_SEARCH_SUFFIX = re.compile(
        r"^(?:can\s+you\s+)?(?:search|serach)\s+(?P<query>.+?)\s+"
        r"(?:in|on)\s+(?:the\s+)?(?:web|internet)\s*[.!?]*$",
        re.IGNORECASE,
    )
    _DESKTOP_FIND_OPEN = re.compile(
        r"\bsearch\s+(?:my\s+|the\s+)?des(?:k)?top\s+and\s+open\s+"
        r"(?:the\s+)?(?P<folder>.+?)(?:\s+folder)?\s*[.!?]*$",
        re.IGNORECASE,
    )
    _DESKTOP_BLANK_TEXT = re.compile(
        r"\b(?:in|on)\s+(?:my\s+|the\s+)?des(?:k)?top\b.*\b"
        r"create\s+(?:a\s+)?blank\s+(?:txt|text)\s+file\b",
        re.IGNORECASE,
    )
    _DESKTOP_OPEN_FILE = re.compile(
        r"\bopen\s+(?:the\s+)?(?:created\s+)?(?P<file>.+?)\s+"
        r"(?:in|on|from)\s+(?:my\s+|the\s+)?des(?:k)?top\s*[.!?]*$",
        re.IGNORECASE,
    )
    _DOWNLOADS_LIST = re.compile(
        r"\b(?:files|contents|folders?)\s+(?:are\s+)?"
        r"(?:in|inside|under|from)\s+(?:my\s+|the\s+)?"
        r"downloads?\s+folder\b|"
        r"\b(?:list|show)\s+(?:me\s+)?(?:my\s+|the\s+)?"
        r"downloads?(?:\s+folder)?\b",
        re.IGNORECASE,
    )
    _CONTEXTUAL_WEB_RESEARCH = re.compile(
        r"^(?:i\s+mean\s+)?(?:can\s+you\s+|please\s+)?"
        r"(?:research|look\s+up|search(?:\s+the\s+(?:web|internet))?)"
        r"(?:\s+about)?\s+(?:that|it|this(?:\s+topic)?)\s*[.!?]*$",
        re.IGNORECASE,
    )

    @staticmethod
    def _normalize_spoken_file_name(value):
        name = str(value or "").strip(" .!?")
        name = re.sub(
            r"\s+(?:txt|text)(?:\s+file)?$", ".txt", name,
            flags=re.IGNORECASE,
        )
        if name.lower().endswith(" file"):
            name = name[:-5].strip()
        if not name or name in {".", ".."}:
            return None
        if any(separator in name for separator in ("/", "\\", ":")):
            return None
        return name

    def resolve(self, user_message):
        text = str(user_message or "").strip()
        if not text:
            return None
        if self._SCREENSHOT.search(text):
            return ToolRequest("capabilities", {"topic": "screenshot"})
        if self._CAMERA.search(text):
            return ToolRequest("app_launcher", {"app_name": "camera"})
        if self._DOWNLOADS_LIST.search(text):
            return ToolRequest("folder", {"path": "downloads"})
        desktop_folder = self._DESKTOP_FIND_OPEN.search(text)
        if desktop_folder:
            folder_name = desktop_folder.group("folder").strip(" .!?")
            if folder_name.lower().endswith(" folder"):
                folder_name = folder_name[:-7].strip()
            return ToolRequest(
                "folder",
                {
                    "path": "desktop",
                    "find": folder_name,
                    "open_match": True,
                },
            )
        if self._DESKTOP_BLANK_TEXT.search(text):
            return ToolRequest(
                "file_write",
                {
                    "file_path": "desktop://blank.txt",
                    "content": "",
                    "fail_if_exists": True,
                },
            )
        desktop_file = self._DESKTOP_OPEN_FILE.search(text)
        if desktop_file:
            file_name = self._normalize_spoken_file_name(
                desktop_file.group("file")
            )
            if file_name:
                return ToolRequest(
                    "app_launcher",
                    {
                        "app_name": "file",
                        "path": f"desktop://{file_name}",
                    },
                )
        memory_search = self._MEMORY_SEARCH.search(text)
        if memory_search:
            query = str(memory_search.group("query") or text).strip(" .!?")
            return ToolRequest("memory_search", {"query": query})
        web_search = (
            self._WEB_SEARCH_PREFIX.search(text)
            or self._WEB_SEARCH_SUFFIX.match(text)
        )
        if web_search:
            query = str(web_search.group("query") or text).strip(" .!?")
            return ToolRequest("web_search", {"query": query})
        application = self._APPLICATION.match(text)
        if application:
            return ToolRequest(
                "app_launcher",
                {"app_name": application.group("app")},
            )
        if self._CALCULATION.fullmatch(text) and any(
            character.isdigit() for character in text
        ):
            return ToolRequest("calculator", {"expression": text})
        if self._DATE_TIME.search(text):
            return ToolRequest("date_time", {})
        if self._CAPABILITIES.search(text):
            return ToolRequest("capabilities", {})
        return None

    def resolve_followup(self, user_message, previous_user_message=None):
        """Resolve explicit contextual research without guessing its subject."""
        text = str(user_message or "").strip()
        previous = str(previous_user_message or "").strip()
        if not text or not previous:
            return None
        if not self._CONTEXTUAL_WEB_RESEARCH.match(text):
            return None
        query = re.sub(
            r"^(?:h+m+|well|okay|ok|so)\s*[,.-]?\s*",
            "",
            previous,
            flags=re.IGNORECASE,
        ).strip()
        if not query:
            return None
        return ToolRequest("web_search", {"query": query})
