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

            print("[Decision Engine] -> SEARCH_MEMORY")

            return Action.SEARCH_MEMORY

        if text.startswith("forget "):

            print("[Decision Engine] -> DELETE_MEMORY")

            return Action.DELETE_MEMORY

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
        # DEFAULT CHAT
        # ============================

        print("[Decision Engine] -> CHAT")

        return Action.CHAT