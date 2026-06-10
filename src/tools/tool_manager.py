class ToolManager:

    def __init__(self):

        self.tools = {}

    def register_tool(self, tool):

        self.tools[tool.name] = tool

    def get_tool(self, tool_name):

        return self.tools.get(tool_name)

    def execute_tool(
        self,
        tool_name,
        **kwargs
    ):

        tool = self.get_tool(tool_name)

        if not tool:
            raise ValueError(
                f"Tool '{tool_name}' not found."
            )

        return tool.execute(**kwargs)