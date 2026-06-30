import json
import logging

from tools.tool_permission import ToolPermission

logger = logging.getLogger(__name__)


class ToolManager:

    def __init__(self):

        self.tools = {}
        self._high_permission_tools = set()

    def register_tool(self, tool):

        self.tools[tool.name] = tool
        if hasattr(tool, 'permission') and tool.permission == ToolPermission.HIGH:
            self._high_permission_tools.add(tool.name)

    def get_tool(self, tool_name):

        return self.tools.get(tool_name)

    def get_tools_by_category(self, category):

        return {
            name: tool
            for name, tool in self.tools.items()
            if tool.category == category
        }

    def get_all_schemas(self):

        return [tool.get_schema() for tool in self.tools.values()]

    def get_schemas_json(self):

        schemas = self.get_all_schemas()
        return json.dumps(schemas, indent=2)

    def is_high_permission(self, tool_name):
        return tool_name in self._high_permission_tools

    def validate_tool_call(self, tool_name, parameters):
        from config.settings import settings

        if tool_name not in self.tools:
            return False, f"Unknown tool: {tool_name}"

        param_str = json.dumps(parameters)
        if len(param_str) > settings.tool_call_max_params_length:
            return False, f"Parameters too long ({len(param_str)} chars)"

        return True, None

    def execute_tool(
        self,
        tool_name,
        **kwargs
    ):

        valid, error = self.validate_tool_call(tool_name, kwargs)
        if not valid:
            return {
                "success": False,
                "error": error
            }

        tool = self.get_tool(tool_name)

        return tool.execute(**kwargs)