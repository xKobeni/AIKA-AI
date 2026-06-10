from models.actions import Action
from models.tool_request import ToolRequest
import re

class Router:

    def __init__(
        self,
        memory_handler,
        chat_handler,
        tool_handler
    ):

        self.memory_handler = memory_handler
        self.chat_handler = chat_handler
        self.tool_handler = tool_handler

    def route(
        self,
        action,
        user_message
    ):

        if action == Action.STORE_MEMORY:

            return (
                self.memory_handler
                .store_memory(user_message)
            )

        if action == Action.LIST_MEMORIES:

            return (
                self.memory_handler
                .list_memories()
            )

        if action == Action.SEARCH_MEMORY:

            return (
                self.memory_handler
                .search_memory(
                    user_message[7:]
                )
            )

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

            return (
                self.memory_handler
                .delete_memory(
                    memory_id
                )
            )

        if action == Action.CHAT:

            return (
                self.chat_handler
                .chat(user_message)
            )
            
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

            else:

                tool_request = ToolRequest(
                    tool_name="memory_search",
                    parameters={
                        "query": user_message
                    }
                )

            return self.tool_handler.handle(
                tool_request
            )