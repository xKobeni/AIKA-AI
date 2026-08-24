from config.settings import settings


class ToolHandler:

    def __init__(
        self, 
        tool_manager,
        tool_response_handler,
        agent_registry=None
    ):
        self.tool_manager = tool_manager
        self.tool_response_handler = tool_response_handler
        self.agent_registry = agent_registry
        self.crawl_max_chars = settings.crawl_content_max_chars

    def refresh_from_settings(self):
        self.crawl_max_chars = settings.crawl_content_max_chars

    def handle(
        self,
        tool_request,
        agent_id=None
    ):

        allowed_tool_names = None
        if agent_id and self.agent_registry:
            profile = self.agent_registry.get(agent_id)
            if profile and profile.allowed_tools:
                allowed_tool_names = set(profile.allowed_tools)

        result = (
            self.tool_manager.execute_tool(
                tool_request.tool_name,
                allowed_tool_names=allowed_tool_names,
                **tool_request.parameters
            )
        )

        user_message = ""

        if "query" in tool_request.parameters:

            user_message = (
                tool_request.parameters["query"]
            )

        elif "expression" in tool_request.parameters:

            user_message = (
                tool_request.parameters["expression"]
            )

        display_result = self._extract_display_result(
            tool_request.tool_name,
            result
        )

        if (
            tool_request.tool_name == "web_search"
            and isinstance(result, dict)
            and not result.get("results")
        ):
            return display_result

        response = (
            self.tool_response_handler
            .generate_response(
                user_message=user_message,
                tool_name=tool_request.tool_name,
                tool_result=display_result
            )
        )

        return response

    def _extract_display_result(
        self,
        tool_name,
        result
    ):

        if not isinstance(result, dict):
            return str(result)

        if tool_name == "calculator":

            if result.get("success"):
                return result.get("result", "")

            return result.get("error", "Calculation failed")

        if tool_name == "file_search":

            paths = result.get("file_paths", [])

            if paths:
                return "\n".join(paths)

            return result.get("error", "No files found")

        if tool_name == "file_read":

            if result.get("success"):
                return result.get("content", "")

            return result.get("error", "Failed to read file")

        if tool_name == "memory_search":

            memories = result.get("memories", [])

            if memories:
                return "\n".join(memories)

            return "No memories found."

        if tool_name == "web_search":

            results = result.get("results", [])

            if results:

                lines = []

                for r in results:

                    lines.append(
                        f"{r.get('title', '')}\n"
                        f"  URL: {r.get('href', r.get('url', ''))}\n"
                        f"  {r.get('body', r.get('snippet', ''))}"
                    )

                return "\n\n".join(lines)

            return result.get(
                "message",
                result.get("error", "No matching results were found.")
            )

        if tool_name == "web_crawl":

            if result.get("success"):

                content = result.get("content", "")

                return (
                    content[:self.crawl_max_chars] + "..."
                    if len(content) > self.crawl_max_chars
                    else content
                )

            return result.get(
                "error",
                "Failed to fetch page."
            )

        return str(result)
