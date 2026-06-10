import re
from models.actions import Action

class DecisionEngine:

    def decide(self, user_input: str):

        text = user_input.lower().strip()

        # MEMORY: store
        if text.startswith("remember "):
            return Action.STORE_MEMORY

        # MEMORY: list
        if text == "memories":
            return Action.LIST_MEMORIES

        # MEMORY: search
        if text.startswith("search "):
            return Action.SEARCH_MEMORY

        # MEMORY: delete
        if text.startswith("forget "):
            return Action.DELETE_MEMORY

        # ----------------------------
        # TOOL: calculator detection
        # ----------------------------
        if re.match(
            r"^[0-9+\-*/(). ]+$",
            text
        ):
            print("[Decision Engine] -> USE_TOOL (calculator)")
            return Action.USE_TOOL

        # DEFAULT: chat
        print("[Decision Engine] -> CHAT")
        return Action.CHAT