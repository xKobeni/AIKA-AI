from models.actions import Action

class Router:

    def __init__(
        self,
        memory_handler,
        chat_handler
    ):

        self.memory_handler = memory_handler
        self.chat_handler = chat_handler

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

            memory_id = int(
                user_message.split()[1]
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