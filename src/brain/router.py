import time
import re

from models.actions import Action
from models.tool_request import ToolRequest

class Router:

    def __init__(
        self,
        memory_handler,
        chat_handler,
        tool_handler,
        conversation_repo=None,
        planner=None,
        executor=None
    ):

        self.memory_handler = memory_handler
        self.chat_handler = chat_handler
        self.tool_handler = tool_handler
        self.conversation_repo = conversation_repo
        self.planner = planner
        self.executor = executor

    def route(
        self,
        action,
        user_message
    ):

        t0 = time.time()

        if action == Action.STORE_MEMORY:

            result = self.memory_handler.store_memory(
                user_message
            )
            print(f"[DEBUG] Route: STORE_MEMORY ({time.time()-t0:.2f}s)")
            return result

        if action == Action.LIST_MEMORIES:

            result = self.memory_handler.list_memories()
            print(f"[DEBUG] Route: LIST_MEMORIES ({time.time()-t0:.2f}s)")
            return result

        if action == Action.SEARCH_MEMORY:

            result = self.memory_handler.search_memory(
                user_message[7:]
            )
            print(f"[DEBUG] Route: SEARCH_MEMORY ({time.time()-t0:.2f}s)")
            return result

        if action == Action.DELETE_MEMORY:

            try:
                memory_id = int(
                    user_message.split()[1]
                )
            except (IndexError, ValueError):
                return (
                    "Please provide a valid memory ID to forget. "
                    "Example: forget 1"
                )

            result = self.memory_handler.delete_memory(
                memory_id
            )
            print(f"[DEBUG] Route: DELETE_MEMORY ({time.time()-t0:.2f}s)")
            return result

        if action == Action.PLAN_EXECUTION:

            if not self.planner or not self.executor:
                return "Planning system is not available."

            plan = self.planner.create_plan(
                user_message
            )

            if plan is None:
                return (
                    "I'm not sure how to break that down. "
                    "Could you be more specific?"
                )

            result = self.executor.execute_plan(plan)
            print(f"[DEBUG] Route: PLAN_EXECUTION ({time.time()-t0:.2f}s)")
            return result

        if action == Action.CLEAR_CONVERSATION:

            self.conversation_repo.clear()
            return "Conversation history cleared."
            
        if action == Action.CHAT:

            result = self.chat_handler.chat(user_message)
            print(f"[DEBUG] Route: CHAT ({time.time()-t0:.2f}s)")
            return result
            
        if action == Action.USE_TOOL:

            if re.match(
                r"^[0-9+\-*/(). ]+$",
                user_message
            ):

                tool_request = ToolRequest(
                    tool_name="calculator",
                    parameters={
                        "expression": user_message
                    }
                )

                print("[DEBUG] Route: USE_TOOL -> calculator")

            elif user_message.lower().startswith(
                "find "
            ):

                tool_request = ToolRequest(
                    tool_name="file_search",
                    parameters={
                        "query": user_message
                    }
                )

                print("[DEBUG] Route: USE_TOOL -> file_search")

            elif user_message.lower().startswith(
                "read "
            ):

                tool_request = ToolRequest(
                    tool_name="file_read",
                    parameters={
                        "file_path": user_message[5:]
                    }
                )

                print("[DEBUG] Route: USE_TOOL -> file_read")

            elif self._is_web_search(user_message):

                tool_request = ToolRequest(
                    tool_name="web_search",
                    parameters={
                        "query": user_message,
                        "max_results": 5
                    }
                )

                print("[DEBUG] Route: USE_TOOL -> web_search")

            elif self._is_referential(user_message):

                tool_request = ToolRequest(
                    tool_name="web_search",
                    parameters={
                        "query": user_message,
                        "max_results": 5
                    }
                )

                print("[DEBUG] Route: USE_TOOL -> web_search (referential)")

            else:

                tool_request = ToolRequest(
                    tool_name="memory_search",
                    parameters={
                        "query": user_message
                    }
                )

                print("[DEBUG] Route: USE_TOOL -> memory_search")

            result = self.tool_handler.handle(tool_request)
            print(f"[DEBUG] Route: Total: {time.time()-t0:.2f}s")
            return result

    @staticmethod
    def _is_referential(text):

        referential_words = [
            " it ", " it'", " that ", " this ",
            " these ", " those ", " they ", " them",
            "what is it", "tell me more",
            "explain", "elaborate", "go on"
        ]
        t = text.lower()
        return any(w in t for w in referential_words)

    @staticmethod
    def _is_web_search(text):
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
        return any(phrase in text.lower() for phrase in web_search_phrases)