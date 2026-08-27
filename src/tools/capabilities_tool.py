from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from tools.tool_availability import is_tool_runtime_enabled


class CapabilitiesTool(BaseTool):
    """Describe only capabilities that exist in the current runtime."""

    description = "Lists the tools currently available to the active AIKA agent"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.LOW
    response_policy = "direct_result"

    def __init__(
        self,
        tool_manager,
        agent_registry=None,
        agent_id_provider=None,
        skill_manager=None,
        session_id_provider=None,
    ):
        self._tool_manager = tool_manager
        self._agent_registry = agent_registry
        self._agent_id_provider = agent_id_provider
        self._skill_manager = skill_manager
        self._session_id_provider = session_id_provider

    @property
    def name(self):
        return "capabilities"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "topic": {
                    "type": "string",
                    "required": False,
                    "description": "Optional capability to check, such as screenshot",
                }
            },
        }

    def _active_agent_id(self):
        if callable(self._agent_id_provider):
            return self._agent_id_provider()
        return None

    def _active_session_id(self):
        if callable(self._session_id_provider):
            return self._session_id_provider()
        return None

    def _available_tools(self):
        allowed = None
        agent_id = self._active_agent_id()
        if agent_id and self._agent_registry is not None:
            profile = self._agent_registry.get(agent_id)
            configured = getattr(profile, "allowed_tools", None)
            if configured:
                allowed = set(configured)

        available = []
        for name, tool in sorted(self._tool_manager.tools.items()):
            if name == self.name:
                continue
            if allowed is not None and name not in allowed:
                continue
            if not is_tool_runtime_enabled(name):
                continue
            available.append({
                "name": name,
                "description": str(getattr(tool, "description", "") or ""),
                "category": getattr(getattr(tool, "category", None), "value", None),
                "permission": getattr(getattr(tool, "permission", None), "value", None),
            })
        return available

    def execute(self, topic=None):
        normalized_topic = str(topic or "").strip().lower()
        if normalized_topic in {"screenshot", "screen capture", "capture screen"}:
            return {
                "success": True,
                "available": False,
                "topic": "screenshot",
                "text": (
                    "I can't take screenshots in this AIKA build because no "
                    "screenshot tool is registered."
                ),
            }

        tools = self._available_tools()
        lines = ["I can currently use these tools:"]
        lines.extend(
            f"- {item['name']}: {item['description']}" for item in tools
        )
        result = {
            "success": True,
            "agent_id": self._active_agent_id(),
            "tools": tools,
            "text": "\n".join(lines),
        }
        if self._skill_manager is not None:
            skills = self._skill_manager.status_items(
                session_id=self._active_session_id(),
                agent_id=self._active_agent_id(),
            )
            issues = [
                {"source": issue.source, "error": issue.error}
                for issue in self._skill_manager.registry.issues
            ]
            active = next(
                (
                    item["id"] for item in skills
                    if item["status"] == "active"
                ),
                None,
            )
            lines.append("Installed skills:")
            if skills:
                lines.extend(
                    f"- {item['id']} [{item['status']}]: {item['description']}"
                    + (
                        f" — {item['reason']}"
                        if item["status"] in {"disabled", "unavailable"}
                        else ""
                    )
                    for item in skills
                )
            else:
                lines.append("- None")
            if issues:
                lines.append(f"Rejected skills: {len(issues)}")
            lines.append(f"Active skill: {active or 'none'}")
            result.update({
                "skills": skills,
                "skill_issues": issues,
                "active_skill": active,
                "text": "\n".join(lines),
            })
        return result
