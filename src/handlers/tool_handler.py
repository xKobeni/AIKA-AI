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

        response = (
            self.tool_response_handler
            .generate_response(
                user_message=user_message,
                tool_name=tool_request.tool_name,
                tool_result=result
            )
        )

        return response