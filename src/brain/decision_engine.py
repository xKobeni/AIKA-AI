import re
import logging

from models.actions import Action

logger = logging.getLogger(__name__)


class DecisionEngine:

    def __init__(self, intent_classifier=None):
        self.intent_classifier = intent_classifier

    def decide(self, user_input: str):

        text = user_input.lower().strip()

        # ============================
        # MEMORY COMMANDS
        # ============================

        if text.startswith("remember "):

            logger.debug("-> STORE_MEMORY")

            return Action.STORE_MEMORY

        if text == "memories":

            logger.debug("-> LIST_MEMORIES")

            return Action.LIST_MEMORIES

        if text.startswith("search "):

            remaining = text[7:]

            web_search_followups = [
                "the internet", "the web",
                "for ", "online", "google"
            ]

            if any(
                remaining.startswith(w)
                or remaining == w
                for w in web_search_followups
            ):

                logger.debug("-> USE_TOOL (web_search)")

                return Action.USE_TOOL

            logger.debug("-> SEARCH_MEMORY")

            return Action.SEARCH_MEMORY

        if text.startswith("forget "):

            logger.debug("-> DELETE_MEMORY")

            return Action.DELETE_MEMORY

        # ============================
        # OS / SHELL COMMANDS
        # ============================

        if text.startswith("run "):

            logger.debug("-> USE_TOOL (shell)")

            return Action.USE_TOOL

        if text.startswith("open "):

            logger.debug("-> USE_TOOL (app_launcher)")

            return Action.USE_TOOL

        if text.startswith("list ") or text.startswith("show "):

            logger.debug("-> USE_TOOL (folder)")

            return Action.USE_TOOL

        if any(text.startswith(p) for p in [
            "system info", "system health",
            "system status", "how's my"
        ]) or any(text == p for p in [
            "system info", "system health",
            "system status"
        ]):

            logger.debug("-> USE_TOOL (system_info)")

            return Action.USE_TOOL

        # ============================
        # PLAN EXECUTION (multi-step)
        # ============================

        multi_step_keywords = [
            "summarize", "analyze",
            "review", "inspect",
            "research", "investigate"
        ]

        multi_step_patterns = [
            "find and ", "read and ",
            "search and "
        ]

        if any(
            kw in text
            for kw in multi_step_keywords
        ) or any(
            text.startswith(p)
            for p in multi_step_patterns
        ):

            logger.debug("-> PLAN_EXECUTION")

            return Action.PLAN_EXECUTION

        # ============================
        # TOOL: CALCULATOR
        # ============================

        if re.match(
            r"^[0-9+\-*/(). ]+$",
            text
        ):

            logger.debug("-> USE_TOOL (calculator)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE SEARCH
        # ============================

        if text.startswith("find "):

            logger.debug("-> USE_TOOL (file_search)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE READ
        # ============================

        if text.startswith("read "):

            logger.debug("-> USE_TOOL (file_read)")

            return Action.USE_TOOL

        # ============================
        # CONFIG COMMANDS
        # ============================

        if text.startswith("!"):

            logger.debug("-> CONFIGURE (%s)", text)

            return Action.CONFIGURE

        # ============================
        # CLEAR CONVERSATION
        # ============================

        if text in (
            "clear history",
            "clear conversation",
            "reset",
            "reset conversation",
            "clear"
        ):

            logger.debug("-> CLEAR_CONVERSATION")

            return Action.CLEAR_CONVERSATION

        # ============================
        # INTENT CLASSIFIER FALLBACK
        # ============================

        if self.intent_classifier:

            result = self.intent_classifier.classify(text)

            action = result["action"]
            tool_name = result.get("tool_name")

            if tool_name:
                logger.debug("-> %s (%s)", action.value, tool_name)
            else:
                logger.debug("-> %s", action.value)

            return action

        return Action.CHAT