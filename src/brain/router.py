import time
import re
import logging

from config.settings import settings
from models.actions import Action
from models.tool_request import ToolRequest

logger = logging.getLogger(__name__)

class Router:

    def __init__(
        self,
        memory_handler,
        chat_handler,
        tool_handler,
        conversation_repo=None,
        planner=None,
        executor=None,
        intent_classifier=None,
        config_handler=None
    ):

        self.memory_handler = memory_handler
        self.chat_handler = chat_handler
        self.tool_handler = tool_handler
        self.conversation_repo = conversation_repo
        self.planner = planner
        self.executor = executor
        self.intent_classifier = intent_classifier
        self.config_handler = config_handler

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
            logger.debug("Route: STORE_MEMORY (%.2fs)", time.time() - t0)
            return result

        if action == Action.LIST_MEMORIES:

            result = self.memory_handler.list_memories()
            logger.debug("Route: LIST_MEMORIES (%.2fs)", time.time() - t0)
            return result

        if action == Action.SEARCH_MEMORY:

            result = self.memory_handler.search_memory(
                user_message[7:]
            )
            logger.debug("Route: SEARCH_MEMORY (%.2fs)", time.time() - t0)
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
            logger.debug("Route: DELETE_MEMORY (%.2fs)", time.time() - t0)
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
            logger.debug("Route: PLAN_EXECUTION (%.2fs)", time.time() - t0)
            return result

        if action == Action.CLEAR_CONVERSATION:

            self.conversation_repo.clear()
            return "Conversation history cleared."

        if action == Action.CONFIGURE:

            if not self.config_handler:
                return "Configuration system is not available."

            result = self.config_handler.handle(user_message)
            logger.debug("Route: CONFIGURE (%.2fs)", time.time() - t0)
            return result

        if action == Action.CHAT:

            result = self.chat_handler.chat(user_message)
            logger.debug("Route: CHAT (%.2fs)", time.time() - t0)
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

                logger.debug("Route: USE_TOOL -> calculator")

            elif user_message.lower().startswith(
                "find "
            ):

                tool_request = ToolRequest(
                    tool_name="file_search",
                    parameters={
                        "query": user_message
                    }
                )

                logger.debug("Route: USE_TOOL -> file_search")

            elif user_message.lower().startswith(
                "read "
            ):

                tool_request = ToolRequest(
                    tool_name="file_read",
                    parameters={
                        "file_path": user_message[5:]
                    }
                )

                logger.debug("Route: USE_TOOL -> file_read")

            elif user_message.lower().startswith("run "):

                tool_request = ToolRequest(
                    tool_name="shell",
                    parameters={
                        "command": user_message[4:].strip()
                    }
                )

                logger.debug("Route: USE_TOOL -> shell")

            elif user_message.lower().startswith("open "):

                tool_request = ToolRequest(
                    tool_name="app_launcher",
                    parameters={
                        "app_name": user_message[5:].strip()
                    }
                )

                logger.debug("Route: USE_TOOL -> app_launcher")

            elif user_message.lower().startswith("list ") or \
                 user_message.lower().startswith("show "):

                prefix = "list " if user_message.lower().startswith("list ") else "show "
                path = user_message[len(prefix):].strip() or "."

                tool_request = ToolRequest(
                    tool_name="folder",
                    parameters={
                        "path": path
                    }
                )

                logger.debug("Route: USE_TOOL -> folder")

            elif any(user_message.lower().startswith(p) for p in [
                "system info", "system health",
                "system status", "how's my"
            ]):

                tool_request = ToolRequest(
                    tool_name="system_info",
                    parameters={}
                )

                logger.debug("Route: USE_TOOL -> system_info")

            else:

                tool_name = "memory_search"

                if self.intent_classifier:
                    result = self.intent_classifier.classify(
                        user_message
                    )
                    tool_name = result.get(
                        "tool_name", "memory_search"
                    )

                if tool_name == "web_search":
                    tool_request = ToolRequest(
                        tool_name="web_search",
                        parameters={
                            "query": user_message,
                            "max_results": settings.web_search_max_results
                        }
                    )
                    logger.debug("Route: USE_TOOL -> web_search")
                elif tool_name == "file_search":
                    tool_request = ToolRequest(
                        tool_name="file_search",
                        parameters={
                            "query": user_message
                        }
                    )
                    logger.debug("Route: USE_TOOL -> file_search")
                else:
                    tool_request = ToolRequest(
                        tool_name="memory_search",
                        parameters={
                            "query": user_message
                        }
                    )
                    logger.debug("Route: USE_TOOL -> memory_search")

            result = self.tool_handler.handle(tool_request)
            logger.debug("Route: Total: %.2fs", time.time() - t0)
            return result

