class ToolHandler:

    def __init__(
        self, 
        tool_manager,
        tool_response_handler
    ):
        self.tool_manager = tool_manager
        self.tool_response_handler = tool_response_handler

    def handle(
        self,
        tool_request
    ):

        result = (
            self.tool_manager.execute_tool(
                tool_request.tool_name,
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

        return str(result)