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
        self._last_model = None
        self._last_reason = None
        self.refresh_from_settings()

    @staticmethod
    def _positive_int(name, default):
        value = getattr(settings, name, default)
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        return default

    @staticmethod
    def _string_list(name, default):
        value = getattr(settings, name, default)
        if not isinstance(value, (list, tuple)):
            return list(default)
        normalized = [str(item).strip().lower() for item in value if str(item).strip()]
        return normalized or list(default)

    def refresh_from_settings(self):
        self.fast = settings.fast_model
        self.smart = settings.smart_model
        self.long_message_words = self._positive_int(
            "model_router_long_message_words", 20
        )
        self.complex_question_words = self._positive_int(
            "model_router_complex_question_words", 12
        )
        self.escalation_iteration = self._positive_int(
            "model_router_escalation_iteration", 2
        )
        self.complex_keywords = self._string_list(
            "model_router_complex_keywords", COMPLEX_KEYWORDS
        )
        self.tool_heavy_prefixes = self._string_list(
            "model_router_tool_heavy_prefixes", TOOL_HEAVY_TASKS
        )

    def select_with_reason(
        self, message, task_type="chat", iteration=0, explicit_model=None
    ):
        if explicit_model:
            self._last_model = explicit_model
            self._last_reason = "explicit_agent_model"
            return explicit_model, self._last_reason

        use_model = self.fast  # default
        reason = "fast_default"

        if task_type in ("intent", "reflection"):
            use_model = self.fast
            reason = f"fast_{task_type}"
        elif task_type in ("plan", "report", "file_content"):
            use_model = self.smart
            reason = f"smart_{task_type}"
        elif task_type == "tool_result_summarize":
            use_model = self.fast
            reason = "fast_tool_result_summarize"
        else:
            text = message.lower().strip()
            words = text.split()

            if any(kw in text for kw in self.complex_keywords):
                logger.debug("ModelRouter: smart (complex keyword)")
                use_model = self.smart
                reason = "smart_complex_keyword"

            elif any(text.startswith(p) for p in self.tool_heavy_prefixes):
                logger.debug("ModelRouter: smart (multi-step task)")
                use_model = self.smart
                reason = "smart_multi_step"

            elif len(words) > self.long_message_words:
                logger.debug("ModelRouter: smart (long message, %d words)", len(words))
                use_model = self.smart
                reason = "smart_long_message"

            elif text.endswith("?") and len(words) > self.complex_question_words:
                logger.debug("ModelRouter: smart (complex question)")
                use_model = self.smart
                reason = "smart_complex_question"

            elif iteration >= self.escalation_iteration:
                logger.debug("ModelRouter: smart (iteration %d, task escalating)", iteration)
                use_model = self.smart
                reason = "smart_iteration_escalation"

            else:
                logger.debug("ModelRouter: fast (simple task)")
                use_model = self.fast

        self._last_model = use_model
        self._last_reason = reason
        return use_model, reason

    def select(
        self, message, task_type="chat", iteration=0, explicit_model=None
    ):
        model, _ = self.select_with_reason(
            message,
            task_type=task_type,
            iteration=iteration,
            explicit_model=explicit_model,
        )
        return model

    def escalate(self, reason="tool failed"):
        logger.debug("ModelRouter: escalate to smart (%s)", reason)
        self._last_model = self.smart
        self._last_reason = f"escalated:{reason}"
        return self.smart

    @property
    def last_selected(self):
        return self._last_model

    @property
    def last_reason(self):
        return self._last_reason

    def get_status(self):
        return {
            "fast": self.fast,
            "smart": self.smart,
            "long_message_words": self.long_message_words,
            "complex_question_words": self.complex_question_words,
            "escalation_iteration": self.escalation_iteration,
            "last_selected": self._last_model,
            "last_reason": self._last_reason,
        }
