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

            file_grep_followups = [
                "in "
            ]

            if any(
                remaining.startswith(w)
                or remaining == w
                for w in web_search_followups
            ):

                logger.debug("-> USE_TOOL (web_search)")

                return Action.USE_TOOL

            if any(
                remaining.startswith(w)
                or remaining == w
                for w in file_grep_followups
            ):

                logger.debug("-> USE_TOOL (file_grep)")

                return Action.USE_TOOL

            logger.debug("-> SEARCH_MEMORY")

            return Action.SEARCH_MEMORY

        if text.startswith("forget "):

            logger.debug("-> DELETE_MEMORY")

            return Action.DELETE_MEMORY

        # ============================
        # SESSION COMMANDS (before generic list/show)
        # ============================

        if text in ("list sessions", "sessions", "show sessions"):

            logger.debug("-> LIST_SESSIONS")

            return Action.LIST_SESSIONS

        if text.startswith("resume "):

            logger.debug("-> RESUME_SESSION")

            return Action.RESUME_SESSION

        if text.startswith("delete session "):

            logger.debug("-> DELETE_SESSION")

            return Action.DELETE_SESSION

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
        # DELEGATION DETECTION
        # ============================

        delegation_patterns = [
            "have the ", "ask the ", "delegate to ",
            "let the ", "get the ", "tell the "
        ]

        if any(text.startswith(p) for p in delegation_patterns):
            logger.debug("-> DELEGATE")
            return Action.DELEGATE

        # ============================
        # ORCHESTRATION DETECTION
        # ============================

        orchestration_patterns = [
            "chain ", "team ", "parallel ",
            "run all ", "use all agents"
        ]

        if any(text.startswith(p) for p in orchestration_patterns):
            logger.debug("-> ORCHESTRATE")
            return Action.ORCHESTRATE

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
        # TOOL: FILE MKDIR (before file_write)
        # ============================

        if any(text.startswith(p) for p in [
            "mkdir ", "create folder ", "create directory "
        ]):

            logger.debug("-> USE_TOOL (file_mkdir)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE WRITE
        # ============================

        if any(text.startswith(p) for p in [
            "create ", "write ", "make ",
            "save ", "save as "
        ]):

            logger.debug("-> USE_TOOL (file_write)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE DELETE
        # ============================

        if text.startswith("delete ") or text.startswith("remove "):

            logger.debug("-> USE_TOOL (file_delete)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE APPEND
        # ============================

        if text.startswith("append ") or text.startswith("add to "):

            logger.debug("-> USE_TOOL (file_append)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE EDIT
        # ============================

        if text.startswith("edit ") or text.startswith("replace "):

            logger.debug("-> USE_TOOL (file_edit)")

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE GREP
        # ============================

        if any(text.startswith(p) for p in [
            "grep ", "search in ", "find in "
        ]):

            logger.debug("-> USE_TOOL (file_grep)")

            return Action.USE_TOOL

        # ============================
        # CONFIG COMMANDS
        # ============================

        if text.startswith("!"):

            logger.debug("-> CONFIGURE (%s)", text)

            return Action.CONFIGURE

        # ============================
        # NEW SESSION
        # ============================

        if text in (
            "new conversation",
            "new session",
            "start fresh",
            "reset session"
        ):

            logger.debug("-> NEW_SESSION")

            return Action.NEW_SESSION

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
        # QUICK CHAT DETECTION (skip LLM classifier)
        # ============================

        chat_keywords = [
            "hello", "hi", "hey", "greetings", "good morning",
            "good afternoon", "good evening", "how are you",
            "what's up", "sup", "yo", "thanks", "thank you",
            "bye", "goodbye", "see you", "nice", "cool",
            "great", "awesome", "perfect", "yes", "no",
            "ok", "okay", "sure", "sounds good", "got it",
            "help", "what can you do", "who are you",
            "tell me a joke", "how's it going"
        ]

        words = text.split()
        is_short = len(words) <= 5
        is_greeting = any(text.startswith(kw) or text == kw for kw in chat_keywords)
        is_question = text.endswith("?") and len(words) <= 8
        is_one_word = len(words) == 1

        if is_short and (is_greeting or is_one_word):
            logger.debug("-> CHAT (quick detection, skipped LLM classifier)")
            return Action.CHAT

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