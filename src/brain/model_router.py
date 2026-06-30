import logging
from config.settings import settings

logger = logging.getLogger(__name__)

COMPLEX_KEYWORDS = [
    "analyze", "research", "compare", "explain why",
    "how does", "write code", "debug", "refactor",
    "summarize", "plan", "step by step", "multi",
    "review", "inspect", "investigate", "evaluate",
    "design", "architect", "optimize", "improve"
]

TOOL_HEAVY_TASKS = [
    "find and", "read and", "search and",
    "check and", "list and", "get and"
]


class ModelRouter:

    def __init__(self):
        self.fast = settings.fast_model
        self.smart = settings.smart_model
        self._last_model = None

    def select(self, message, task_type="chat", iteration=0):
        if task_type in ("intent", "reflection"):
            return self.fast

        if task_type in ("plan", "report", "file_content"):
            return self.smart

        if task_type == "tool_result_summarize":
            return self.fast

        text = message.lower().strip()
        words = text.split()

        if any(kw in text for kw in COMPLEX_KEYWORDS):
            logger.debug("ModelRouter: smart (complex keyword)")
            return self.smart

        if any(text.startswith(p) for p in TOOL_HEAVY_TASKS):
            logger.debug("ModelRouter: smart (multi-step task)")
            return self.smart

        if len(words) > 20:
            logger.debug("ModelRouter: smart (long message, %d words)", len(words))
            return self.smart

        if text.endswith("?") and len(words) > 12:
            logger.debug("ModelRouter: smart (complex question)")
            return self.smart

        if iteration >= 2:
            logger.debug("ModelRouter: smart (iteration %d, task escalating)", iteration)
            return self.smart

        logger.debug("ModelRouter: fast (simple task)")
        return self.fast

    def escalate(self, reason="tool failed"):
        logger.debug("ModelRouter: escalate to smart (%s)", reason)
        return self.smart

    @property
    def last_selected(self):
        return self._last_model

    def get_status(self):
        return {
            "fast": self.fast,
            "smart": self.smart,
            "last_selected": self._last_model
        }
