class ToolHandler:

    def __init__(self, tool_manager):
        self.tool_manager = tool_manager

    def handle(self, tool_request):
        return self.tool_manager.execute_tool(
            tool_request.tool_name,
            **tool_request.parameters
        )