import json
import os
import logging
from datetime import datetime

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

    def get_native_tool_schemas(self):
        return [tool.get_native_schema() for tool in self.tools.values()]

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

    def _check_confirmation(self, tool_name, parameters):
        from config.settings import settings

        if not settings.tool_call_confirm_high_permission:
            return True

        if not self.is_high_permission(tool_name):
            return True

        param_preview = json.dumps(parameters, indent=2)
        if len(param_preview) > 500:
            param_preview = param_preview[:500] + "..."

        print(f"\n{'='*50}")
        print(f"HIGH PERMISSION TOOL REQUEST")
        print(f"Tool: {tool_name}")
        print(f"Parameters:\n{param_preview}")
        print(f"{'='*50}")

        try:
            answer = input("Execute? [y/N]: ").strip().lower()
            return answer in ("y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False

    def _audit_log(self, tool_name, parameters, result, agent_id=None):
        from config.settings import settings

        if not settings.audit_log_enabled:
            return

        param_preview = json.dumps(parameters)
        if len(param_preview) > 200:
            param_preview = param_preview[:200] + "..."

        success = result.get("success", False) if isinstance(result, dict) else False
        error = result.get("error", "") if isinstance(result, dict) else ""

        entry = {
            "timestamp": datetime.now().isoformat(),
            "tool": tool_name,
            "parameters": param_preview,
            "success": success,
            "error": str(error)[:200] if error else "",
            "agent_id": agent_id,
        }

        try:
            log_dir = os.path.dirname(settings.audit_log_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)

            with open(settings.audit_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.warning("Failed to write audit log: %s", e)

    def execute_tool(
        self,
        tool_name,
        allowed_tool_names=None,
        agent_id=None,
        **kwargs
    ):

        valid, error = self.validate_tool_call(tool_name, kwargs)
        if not valid:
            return {
                "success": False,
                "error": error
            }

        if allowed_tool_names is not None and tool_name not in allowed_tool_names:
            return {
                "success": False,
                "error": f"Tool '{tool_name}' is not available for this agent."
            }

        if not self._check_confirmation(tool_name, kwargs):
            return {
                "success": False,
                "error": "Execution cancelled by user."
            }

        tool = self.get_tool(tool_name)
        result = tool.execute(**kwargs)

        self._audit_log(tool_name, kwargs, result, agent_id=agent_id)

        return result