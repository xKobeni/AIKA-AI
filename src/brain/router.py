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
        config_handler=None,
        llm=None
    ):

        self.memory_handler = memory_handler
        self.chat_handler = chat_handler
        self.tool_handler = tool_handler
        self.conversation_repo = conversation_repo
        self.planner = planner
        self.executor = executor
        self.intent_classifier = intent_classifier
        self.config_handler = config_handler
        self.llm = llm

    def route(
        self,
        action,
        user_message
    ):

        t0 = time.time()
        text = user_message.strip()

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

            result = self.chat_handler.chat(
                user_message,
                intent=action.value
            )
            logger.debug("Route: CHAT (%.2fs)", time.time() - t0)
            return result
            
        if action == Action.USE_TOOL:

            if re.match(
                r"^[0-9+\-*/(). ]+$",
                text
            ):

                tool_request = ToolRequest(
                    tool_name="calculator",
                    parameters={
                        "expression": text
                    }
                )

                logger.debug("Route: USE_TOOL -> calculator")

            elif text.lower().startswith(
                "find "
            ):

                tool_request = ToolRequest(
                    tool_name="file_search",
                    parameters={
                        "query": text
                    }
                )

                logger.debug("Route: USE_TOOL -> file_search")

            elif text.lower().startswith(
                "read "
            ):

                tool_request = ToolRequest(
                    tool_name="file_read",
                    parameters={
                        "file_path": text[5:]
                    }
                )

                logger.debug("Route: USE_TOOL -> file_read")

            elif text.lower().startswith("run "):

                tool_request = ToolRequest(
                    tool_name="shell",
                    parameters={
                        "command": text[4:].strip()
                    }
                )

                logger.debug("Route: USE_TOOL -> shell")

            elif text.lower().startswith("open "):

                tool_request = ToolRequest(
                    tool_name="app_launcher",
                    parameters={
                        "app_name": text[5:].strip()
                    }
                )

                logger.debug("Route: USE_TOOL -> app_launcher")

            elif text.lower().startswith("list ") or \
                 text.lower().startswith("show "):

                prefix = "list " if text.lower().startswith("list ") else "show "
                path = text[len(prefix):].strip() or "."

                tool_request = ToolRequest(
                    tool_name="folder",
                    parameters={
                        "path": path
                    }
                )

                logger.debug("Route: USE_TOOL -> folder")

            elif any(text.lower().startswith(p) for p in [
                "system info", "system health",
                "system status", "how's my"
            ]):

                tool_request = ToolRequest(
                    tool_name="system_info",
                    parameters={}
                )

                logger.debug("Route: USE_TOOL -> system_info")

            elif text.lower().startswith("mkdir ") or \
                 text.lower().startswith("create folder ") or \
                 text.lower().startswith("create directory "):

                if text.lower().startswith("mkdir "):
                    dir_path = text[6:].strip()
                elif text.lower().startswith("create folder "):
                    dir_path = text[14:].strip()
                else:
                    dir_path = text[17:].strip()

                tool_request = ToolRequest(
                    tool_name="file_mkdir",
                    parameters={
                        "dir_path": dir_path
                    }
                )

                logger.debug("Route: USE_TOOL -> file_mkdir")

            elif any(text.lower().startswith(p) for p in [
                "create ", "write ", "make ",
                "save ", "save as "
            ]):

                prefix = None
                for p in ["save as ", "save ", "create ", "write ", "make "]:
                    if text.lower().startswith(p):
                        prefix = p
                        break

                rest = text[len(prefix):].strip()

                file_path = None
                content = rest

                if " as " in rest:
                    parts = rest.split(" as ", 1)
                    content = parts[0].strip()
                    file_path = parts[1].strip()
                elif " to " in rest:
                    parts = rest.split(" to ", 1)
                    content = parts[0].strip()
                    file_path = parts[1].strip()
                elif "." in rest.split()[-1] if rest.split() else False:
                    words = rest.split()
                    file_path = words[-1]
                    content = " ".join(words[:-1])

                if not file_path:
                    content_lower = content.lower()
                    if "todo" in content_lower:
                        file_path = "todo_list.html"
                    elif "grocery" in content_lower or "shopping" in content_lower:
                        file_path = "grocery_list.html"
                    elif "note" in content_lower:
                        file_path = "notes.txt"
                    else:
                        file_path = "output.txt"

                if not self._looks_like_code(content) and self.llm:
                    logger.debug("Route: Generating content with LLM")
                    content = self._generate_file_content(content)

                tool_request = ToolRequest(
                    tool_name="file_write",
                    parameters={
                        "file_path": file_path,
                        "content": content
                    }
                )

                logger.debug("Route: USE_TOOL -> file_write")

            elif text.lower().startswith("delete ") or \
                 text.lower().startswith("remove "):

                prefix = "delete " if text.lower().startswith("delete ") else "remove "
                file_path = text[len(prefix):].strip()

                tool_request = ToolRequest(
                    tool_name="file_delete",
                    parameters={
                        "file_path": file_path
                    }
                )

                logger.debug("Route: USE_TOOL -> file_delete")

            elif text.lower().startswith("append ") or \
                 text.lower().startswith("add to "):

                prefix = "append " if text.lower().startswith("append ") else "add to "
                rest = text[len(prefix):].strip()

                file_path = None
                content = rest

                if " to " in rest:
                    parts = rest.split(" to ", 1)
                    content = parts[0].strip()
                    file_path = parts[1].strip()
                elif "." in rest.split()[-1] if rest.split() else False:
                    words = rest.split()
                    file_path = words[-1]
                    content = " ".join(words[:-1])

                if not file_path:
                    file_path = "output.txt"

                tool_request = ToolRequest(
                    tool_name="file_append",
                    parameters={
                        "file_path": file_path,
                        "content": content
                    }
                )

                logger.debug("Route: USE_TOOL -> file_append")

            elif text.lower().startswith("edit ") or \
                 text.lower().startswith("replace "):

                if text.lower().startswith("replace "):
                    rest = text[8:].strip()
                    if " with " in rest:
                        parts = rest.split(" with ", 1)
                        old_text = parts[0].strip()
                        remainder = parts[1].strip()
                        if " in " in remainder:
                            parts2 = remainder.split(" in ", 1)
                            new_text = parts2[0].strip()
                            file_path = parts2[1].strip()
                        else:
                            new_text = remainder
                            file_path = "output.txt"
                    else:
                        old_text = rest
                        new_text = ""
                        file_path = "output.txt"
                else:
                    rest = text[5:].strip()
                    if " with " in rest:
                        parts = rest.split(" with ", 1)
                        old_text = parts[0].strip()
                        remainder = parts[1].strip()
                        if " in " in remainder:
                            parts2 = remainder.split(" in ", 1)
                            new_text = parts2[0].strip()
                            file_path = parts2[1].strip()
                        else:
                            new_text = remainder
                            file_path = "output.txt"
                    else:
                        old_text = rest
                        new_text = ""
                        file_path = "output.txt"

                tool_request = ToolRequest(
                    tool_name="file_edit",
                    parameters={
                        "file_path": file_path,
                        "old_text": old_text,
                        "new_text": new_text
                    }
                )

                logger.debug("Route: USE_TOOL -> file_edit")

            elif text.lower().startswith("grep ") or \
                 text.lower().startswith("search in ") or \
                 text.lower().startswith("find in "):

                if text.lower().startswith("grep "):
                    query = text[5:].strip()
                elif text.lower().startswith("search in "):
                    query = text[10:].strip()
                else:
                    query = text[8:].strip()

                file_path = "."
                if " in " in query:
                    parts = query.split(" in ", 1)
                    query = parts[0].strip()
                    file_path = parts[1].strip()

                tool_request = ToolRequest(
                    tool_name="file_grep",
                    parameters={
                        "query": query,
                        "path": file_path
                    }
                )

                logger.debug("Route: USE_TOOL -> file_grep")

            else:

                tool_name = "memory_search"

                if self.intent_classifier:
                    result = self.intent_classifier.classify(
                        text
                    )
                    tool_name = result.get(
                        "tool_name", "memory_search"
                    )

                if tool_name == "web_search":
                    tool_request = ToolRequest(
                        tool_name="web_search",
                        parameters={
                            "query": text,
                            "max_results": settings.web_search_max_results
                        }
                    )
                    logger.debug("Route: USE_TOOL -> web_search")
                elif tool_name == "file_search":
                    tool_request = ToolRequest(
                        tool_name="file_search",
                        parameters={
                            "query": text
                        }
                    )
                    logger.debug("Route: USE_TOOL -> file_search")
                else:
                    tool_request = ToolRequest(
                        tool_name="memory_search",
                        parameters={
                            "query": text
                        }
                    )
                    logger.debug("Route: USE_TOOL -> memory_search")

            result = self.tool_handler.handle(tool_request)
            logger.debug("Route: Total: %.2fs", time.time() - t0)
            return result

    def _looks_like_code(self, text):
        text_lower = text.lower().strip()
        if any(tag in text_lower for tag in [
            "<html", "<div", "<style", "<body",
            "<head", "<!doctype", "<ul", "<li"
        ]):
            return True
        if any(keyword in text_lower for keyword in [
            "function ", "const ", "var ", "let ",
            "def ", "class ", "import ", "from ",
            "return ", "if ", "for ", "while "
        ]):
            return True
        if "{" in text and "}" in text:
            return True
        if ": " in text and any(
            line.strip().endswith(";")
            for line in text.split("\n")
        ):
            return True
        return False

    def _generate_file_content(self, description):
        prompt = (
            f"Generate the complete file content for this request. "
            f"Return ONLY the raw file content, no explanations, "
            f"no markdown code blocks, no backticks. "
            f"If it's HTML, include proper DOCTYPE, head, and body. "
            f"If it's CSS, include proper selectors and properties. "
            f"Request: {description}"
        )
        return self.llm.generate(prompt)

