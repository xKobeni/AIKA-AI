import re

from models.actions import Action


class DecisionEngine:

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

                print(
                    "[Decision Engine] -> USE_TOOL (web_search)"
                )

                return Action.USE_TOOL

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
        # TOOL: WEB SEARCH
        # ============================

        web_search_phrases = [
            "weather",
            "forecast",
            "search the internet",
            "search for ",
            "look up ",
            "find online",
            "google ",
            "latest news",
            "current ",
            "who is ",
            "what is a ",
            "where is ",
            "how to ",
            "when did ",
            "define ",
            "meaning of",
            "news about",
            "information about",
            "web search",
            "search online",
            "browse "
        ]

        if any(
            phrase in text
            for phrase in web_search_phrases
        ):
            print(
                "[Decision Engine] -> USE_TOOL (web_search)"
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

        return Action.CHAT