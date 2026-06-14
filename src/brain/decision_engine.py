import re

from models.actions import Action


class DecisionEngine:

    def __init__(self, llm=None):
        self.llm = llm

    def decide(self, user_input: str):

        text = user_input.lower().strip()

        # ============================
        # MEMORY COMMANDS
        # ============================

        if text.startswith("remember "):

            print("[Decision Engine] -> STORE_MEMORY")

            return Action.STORE_MEMORY

        if text == "memories":

            print("[Decision Engine] -> LIST_MEMORIES")

            return Action.LIST_MEMORIES

        if text.startswith("search "):

            print("[Decision Engine] -> SEARCH_MEMORY")

            return Action.SEARCH_MEMORY

        if text.startswith("forget "):

            print("[Decision Engine] -> DELETE_MEMORY")

            return Action.DELETE_MEMORY

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

            print(
                "[Decision Engine] -> PLAN_EXECUTION"
            )

            return Action.PLAN_EXECUTION

        # ============================
        # TOOL: CALCULATOR
        # ============================

        if re.match(
            r"^[0-9+\-*/(). ]+$",
            text
        ):

            print(
                "[Decision Engine] -> USE_TOOL (calculator)"
            )

            return Action.USE_TOOL

        # ============================
        # TOOL: MEMORY SEARCH
        # ============================

        memory_phrases = [

            "what projects",

            "what project",

            "what am i working on",

            "working on",

            "what do you know about me",

            "what do you know",

            "tell me about me",

            "what have i told you",

            "what is my",

            "what are my",

            "favorite",

            "preferences",

            "my goals",

            "my goal",

            "my plans",

            "my plan",

            " tell me about",

            "what is",

            "project",

            "projects",

            "goal",

            "goals",

            "plan",

            "plans"
        ]

        if any(
            phrase in text
            for phrase in memory_phrases
        ):

            print(
                "[Decision Engine] -> USE_TOOL (memory_search)"
            )

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE SEARCH
        # ============================

        if text.startswith("find "):

            print(
                "[Decision Engine] -> USE_TOOL (file_search)"
            )

            return Action.USE_TOOL

        # ============================
        # TOOL: FILE READ
        # ============================

        if text.startswith("read "):

            print(
                "[Decision Engine] -> USE_TOOL (file_read)"
            )

            return Action.USE_TOOL

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

            print("[Decision Engine] -> CLEAR_CONVERSATION")

            return Action.CLEAR_CONVERSATION

        # ============================
        # LLM FALLBACK
        # ============================

        return self._llm_fallback(text)

    def _llm_fallback(self, text):

        if not self.llm:

            print("[Decision Engine] -> CHAT (no LLM)")

            return Action.CHAT

        prompt = f"""
            Classify the user's intent into exactly one action:

            CHAT: general conversation, greetings, casual talk, opinions
            STORE_MEMORY: user is sharing personal info, facts, preferences, goals about themselves
            SEARCH_MEMORY: user is asking what you know about them, or asking about stored info
            LIST_MEMORIES: user wants to see all stored memories
            DELETE_MEMORY: user wants to delete or forget something
            USE_TOOL: user wants a calculation or information lookup
            CLEAR_CONVERSATION: user wants to reset or clear chat history
            PLAN_EXECUTION: user wants to summarize, analyze, review, inspect, or research something

            User message: "{text}"

            Return ONLY the action name (e.g., CHAT).
            """

        response = self.llm.generate(prompt).strip().upper()

        for action in Action:

            if action.value.upper() == response:

                print(f"[Decision Engine] -> {action.value} (LLM)")

                return action

        print("[Decision Engine] -> CHAT (fallback)")

        return Action.CHAT