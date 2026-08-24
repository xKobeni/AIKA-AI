import re
import logging

from models.actions import Action

logger = logging.getLogger(__name__)


CONVERSATIONAL_STARTERS = {
    "me", "us", "a", "an", "the", "some", "more", "new", "your", "my",
    "him", "her", "them", "it", "one", "two", "three", "that", "this",
    "good", "great", "something", "anything", "everything", "nothing",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _looks_like_file_op(text, prefix_len):
    """
    After stripping a command prefix, decide whether the remainder looks like a
    genuine file/OS operation (has a path/filename/app name) vs. a natural
    language phrase that just happens to start with a command word.
    """
    remainder = text[prefix_len:].strip()
    if not remainder:
        return False

    # Common natural-language non-file suffixes that indicate a conversation
    first_word = remainder.split()[0].lower().rstrip(".,!?")
    if first_word in CONVERSATIONAL_STARTERS:
        return False

    # If it contains a dot-extension it's very likely a file
    if re.search(r'\.[a-zA-Z]{1,5}(\s|$|/|\\)', remainder):
        return True

    # If it contains a path separator it's a file op
    if "/" in remainder or "\\" in remainder:
        return True

    # Prefixes that are ONLY meaningful in a file context
    FILE_INDICATIVE_WORDS = {
        "file", "files", "folder", "folders", "directory", "directories",
        "dir", "path",
        "script", "log", "config", "txt", "csv", "json",
        "py", "js", "html", "css", "md",
    }
    words = {w.lower().rstrip(".,!?") for w in remainder.split()}
    if words & FILE_INDICATIVE_WORDS:
        return True

    return False


def _is_conversational_question(text):
    """
    True when the message is clearly a conversational / personal question
    that should NOT trigger a web search.
    """
    PERSONAL_INDICATORS = [
        "my ", "mine ", "i ", "our ", "we ", "me ",
        "tell me", "do you", "can you", "are you", "would you",
        "what do you think", "what do you know",
        "what do you remember", "what did i",
        "what did we", "how do you feel", "how are you",
        "do you remember", "do you know me",
    ]
    return any(text.startswith(p) or p in text for p in PERSONAL_INDICATORS)


def _is_stable_comparison_question(text):
    """Recognize narrow conceptual comparisons that need no personal memory."""
    if not re.search(
        r"\b(?:what(?:'s|s|\s+is)\s+|tell\s+me\s+)?"
        r"(?:the\s+)?difference\s+between\b",
        text,
    ):
        return False
    if re.search(
        r"\b(?:latest|current|today|newest|recent|price|release|"
        r"20\d{2})\b",
        text,
    ):
        return False
    return not re.search(r"\b(?:my|our)\b", text)


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
                remaining.startswith(w) or remaining == w
                for w in web_search_followups
            ):
                logger.debug("-> USE_TOOL (web_search)")
                return Action.USE_TOOL

            if any(
                remaining.startswith(w) or remaining == w
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
        # AGENT MANAGEMENT COMMANDS
        # Must come before generic "show"/"list" routing
        # ============================

        if text.startswith("show agent ") or text.startswith("list agent"):
            # Let brain.py command handlers deal with these
            logger.debug("-> CHAT (agent management passthrough)")
            return Action.CHAT

        # ============================
        # OS / SHELL COMMANDS
        # ============================

        if text.startswith("run "):
            logger.debug("-> USE_TOOL (shell)")
            return Action.USE_TOOL

        # "open" only routes to app_launcher if it looks like an application name
        if text.startswith("open "):
            remainder = text[5:].strip()
            first_word = remainder.split()[0].rstrip(".,!?") if remainder else ""
            if (
                _looks_like_file_op(text, 5)
                or (remainder and first_word not in CONVERSATIONAL_STARTERS)
            ):
                logger.debug("-> USE_TOOL (app_launcher)")
                return Action.USE_TOOL
            # Otherwise fall through to classifier / chat

        # "list" / "show" only routes to folder tool if it looks like a path request
        if text.startswith("list ") or text.startswith("show "):
            prefix_len = 5  # "list " or "show "
            if _looks_like_file_op(text, prefix_len):
                logger.debug("-> USE_TOOL (folder)")
                return Action.USE_TOOL
            # Otherwise fall through to classifier / chat

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
        # Only when there is a clear target object in the request
        # ============================

        multi_step_patterns = [
            "find and ", "read and ",
            "search and "
        ]

        if any(text.startswith(p) for p in multi_step_patterns):
            logger.debug("-> PLAN_EXECUTION")
            return Action.PLAN_EXECUTION

        # Keywords only trigger plan execution if they reference a clear external target
        multi_step_keywords = [
            "analyze", "research", "compare", "investigate"
        ]
        multi_step_target_indicators = [
            " the ", " this ", " my ", " that ", " these ",
            " file", " code", " folder", " repo", " website",
            " url", " link", " article", " page", " log",
        ]

        if any(kw in text for kw in multi_step_keywords):
            if any(ind in text for ind in multi_step_target_indicators):
                logger.debug("-> PLAN_EXECUTION")
                return Action.PLAN_EXECUTION
            # No clear target → fall through to LLM classifier

        # ============================
        # TOOL: CALCULATOR
        # ============================

        if re.match(r"^[0-9+\-*/(). ]+$", text):
            logger.debug("-> USE_TOOL (calculator)")
            return Action.USE_TOOL

        # ============================
        # TOOL: FILE SEARCH
        # Only route if looks like a file-system search
        # ============================

        if text.startswith("find "):
            if _looks_like_file_op(text, 5):
                logger.debug("-> USE_TOOL (file_search)")
                return Action.USE_TOOL
            # Otherwise fall through to classifier / chat

        # ============================
        # TOOL: FILE READ
        # ============================

        if text.startswith("read "):
            if _looks_like_file_op(text, 5):
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
        # Only route if remainder looks like a file operation
        # ============================

        if any(text.startswith(p) for p in [
            "write ", "save ", "save as "
        ]):
            for p in ["save as ", "save ", "write "]:
                if text.startswith(p):
                    if _looks_like_file_op(text, len(p)):
                        logger.debug("-> USE_TOOL (file_write)")
                        return Action.USE_TOOL
                    break

        # "create" is very conversational — only route to file_write when clearly a file
        if text.startswith("create "):
            if _looks_like_file_op(text, 7):
                logger.debug("-> USE_TOOL (file_write)")
                return Action.USE_TOOL

        # "make" similarly
        if text.startswith("make "):
            if _looks_like_file_op(text, 5):
                logger.debug("-> USE_TOOL (file_write)")
                return Action.USE_TOOL

        # ============================
        # TOOL: FILE DELETE
        # ============================

        if text.startswith("delete ") or text.startswith("remove "):
            prefix_len = 7 if text.startswith("delete ") else 7
            if _looks_like_file_op(text, prefix_len):
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
        is_one_word = len(words) == 1

        if is_short and (is_greeting or is_one_word):
            logger.debug("-> CHAT (quick detection, skipped LLM classifier)")
            return Action.CHAT

        if _is_stable_comparison_question(text):
            logger.debug("-> CHAT (stable conceptual comparison)")
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
