from models.actions import Action

class DecisionEngine:

    def decide(self, user_input: str):

        text = user_input.lower().strip()

        if text.startswith("remember "):
            return Action.STORE_MEMORY

        if text == "memories":
            return Action.LIST_MEMORIES

        if text.startswith("search "):
            return Action.SEARCH_MEMORY

        if text.startswith("forget "):
            return Action.DELETE_MEMORY

        return Action.CHAT