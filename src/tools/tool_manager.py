import json
import os
import logging
import re
from datetime import datetime

from tools.tool_permission import ToolPermission

logger = logging.getLogger(__name__)

_SENSITIVE_KEYS = {
    "api_key", "apikey", "authorization", "content", "credential",
    "new_text", "old_text", "password", "secret", "token",
}
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?:^|[_-])(?:api[_-]?key|auth(?:orization)?|credential|password|passwd|"
    r"private[_-]?key|secret|token)(?:$|[_-])"
)
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|password|secret|token)\s*[=:]\s*)"
    r"([^\s,;]+)"
)


def _redact_sensitive(value, key=None):
    if key and (
        key.lower() in _SENSITIVE_KEYS
        or _SENSITIVE_KEY_PATTERN.search(key)
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            item_key: _redact_sensitive(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE_PATTERN.sub(r"\1[REDACTED]", value)
    return value


class ToolManager:

    def __init__(self, confirmation_handler=None, event_handler=None):

        self.tools = {}
        self._high_permission_tools = set()
        self._confirmation_handler = confirmation_handler
        self._event_handler = event_handler

    def set_confirmation_handler(self, handler):
        self._confirmation_handler = handler

    def set_event_handler(self, handler):
        self._event_handler = handler

    def _emit_event(self, event_type, payload):
        if self._event_handler is None:
            return
        try:
            self._event_handler(event_type, payload)
        except Exception as exc:
            logger.warning(
                "Tool event handler failed: %s", type(exc).__name__
            )

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

        try:
            param_str = json.dumps(parameters, default=str)
        except Exception:
            return False, "Tool parameters could not be serialized"
        if len(param_str) > settings.tool_call_max_params_length:
            return False, f"Parameters too long ({len(param_str)} chars)"

        return True, None

    def _check_confirmation(self, tool_name, parameters):
        from config.settings import settings

        if not settings.tool_call_confirm_high_permission:
            return True

        if not self.is_high_permission(tool_name):
            return True

        safe_parameters = _redact_sensitive(parameters)
        if self._confirmation_handler is not None:
            try:
                return bool(
                    self._confirmation_handler(tool_name, safe_parameters)
                )
            except Exception as exc:
                logger.warning(
                    "Tool confirmation handler failed closed: %s",
                    type(exc).__name__,
                )
                return False

        param_preview = json.dumps(
            safe_parameters, indent=2, default=str
        )
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

        param_preview = json.dumps(
            _redact_sensitive(parameters), default=str
        )
        if len(param_preview) > 200:
            param_preview = param_preview[:200] + "..."

        success = result.get("success", False) if isinstance(result, dict) else False
        error = result.get("error", "") if isinstance(result, dict) else ""
        error = _redact_sensitive(str(error)) if error else ""

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

        self._emit_event("tool_request", {
            "tool_name": tool_name,
            "parameters": _redact_sensitive(kwargs),
        })

        if not self._check_confirmation(tool_name, kwargs):
            result = {
                "success": False,
                "error": "Execution cancelled by user."
            }
            self._emit_event("tool_result", {
                "tool_name": tool_name,
                "success": False,
                "error": result["error"],
            })
            return result

        tool = self.get_tool(tool_name)
        try:
            result = tool.execute(**kwargs)
            if not isinstance(result, dict):
                result = {
                    "success": False,
                    "error": "Tool returned an invalid result"
                }
        except Exception as exc:
            logger.error(
                "Tool '%s' execution failed: %s",
                tool_name,
                type(exc).__name__,
            )
            result = {
                "success": False,
                "error": f"Tool execution failed: {type(exc).__name__}"
            }

        self._audit_log(tool_name, kwargs, result, agent_id=agent_id)
        self._emit_event("tool_result", {
            "tool_name": tool_name,
            "success": bool(result.get("success", False)),
            "error": _redact_sensitive(str(result.get("error", ""))),
        })
        return result
