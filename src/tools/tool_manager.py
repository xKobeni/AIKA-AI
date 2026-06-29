class ToolManager:

    def __init__(self):

        self.tools = {}

    def register_tool(self, tool):

        self.tools[tool.name] = tool

    def get_tool(self, tool_name):

        return self.tools.get(tool_name)

    def get_tools_by_category(self, category):

        return {
            name: tool
            for name, tool in self.tools.items()
            if tool.category == category
        }

    def execute_tool(
        self,
        tool_name,
        **kwargs
    ):

        tool = self.get_tool(tool_name)

        if not tool:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not available"
            }

        return tool.execute(**kwargs)