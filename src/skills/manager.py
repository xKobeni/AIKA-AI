"""Session-scoped activation and reporting for local AIKA skills."""

from threading import RLock

from tools.tool_availability import is_tool_runtime_enabled


class SkillManager:
    """Activate at most one validated skill per in-memory session."""

    def __init__(self, registry, *, tool_manager=None, agent_registry=None):
        self.registry = registry
        self.tool_manager = tool_manager
        self.agent_registry = agent_registry
        self._active_by_session: dict[str, str] = {}
        self._lock = RLock()

    def _agent_profile(self, agent_id):
        if self.agent_registry is None:
            return None
        return self.agent_registry.get(agent_id)

    def availability(self, skill, agent_id):
        if not skill.enabled:
            return False, "disabled by its manifest"
        if skill.allowed_agents is not None and agent_id not in skill.allowed_agents:
            return False, f"not allowed for agent '{agent_id}'"

        profile = self._agent_profile(agent_id)
        if self.agent_registry is not None and profile is None:
            return False, f"unknown agent '{agent_id}'"
        configured = getattr(profile, "allowed_tools", None)
        registered = (
            set(self.tool_manager.tools)
            if self.tool_manager is not None
            else set()
        )

        missing = [
            name for name in skill.required_tools
            if name not in registered
        ]
        if missing:
            return False, "missing required tools: " + ", ".join(missing)
        disabled = [
            name for name in skill.required_tools
            if not is_tool_runtime_enabled(name)
        ]
        if disabled:
            return False, "disabled required tools: " + ", ".join(disabled)
        if configured:
            denied = [
                name for name in skill.required_tools
                if name not in configured
            ]
            if denied:
                return False, "agent cannot use required tools: " + ", ".join(denied)
        return True, "available"

    def activate(self, skill_id, *, session_id, agent_id):
        skill = self.registry.get(skill_id)
        if skill is None:
            return False, f"Skill '{str(skill_id or '').strip()}' was not found."
        if not str(session_id or "").strip():
            return False, "A current session is required to activate a skill."
        available, reason = self.availability(skill, agent_id)
        if not available:
            return False, f"Skill '{skill.id}' cannot be activated: {reason}."
        with self._lock:
            self._active_by_session[str(session_id)] = skill.id
        return True, f"Activated skill `{skill.id}` for this session."

    def deactivate(self, session_id):
        with self._lock:
            skill_id = self._active_by_session.pop(str(session_id or ""), None)
        if skill_id is None:
            return False, "No skill is active in this session."
        return True, f"Deactivated skill `{skill_id}` for this session."

    def active_skill(self, *, session_id, agent_id):
        with self._lock:
            skill_id = self._active_by_session.get(str(session_id or ""))
        if skill_id is None:
            return None
        skill = self.registry.get(skill_id)
        if skill is None or not self.availability(skill, agent_id)[0]:
            with self._lock:
                self._active_by_session.pop(str(session_id or ""), None)
            return None
        return skill

    def prompt_for(self, *, session_id, agent_id):
        skill = self.active_skill(session_id=session_id, agent_id=agent_id)
        if skill is None:
            return ""
        required = ", ".join(skill.required_tools) or "none"
        return (
            f"=== ACTIVE SKILL: {skill.name} ({skill.id}) ===\n"
            "Task-specific guidance only; AIKA safety, grounding, and tool "
            "permissions prevail.\n"
            f"{skill.instructions}\n\n"
            f"Declared required tools: {required}. Script references remain "
            "text unless an already permitted AIKA tool is deliberately selected."
        )

    def status_items(self, *, session_id, agent_id):
        active = self.active_skill(session_id=session_id, agent_id=agent_id)
        items = []
        for skill in self.registry.get_all():
            available, reason = self.availability(skill, agent_id)
            if active is not None and active.id == skill.id:
                status = "active"
            elif available:
                status = "available"
            elif not skill.enabled:
                status = "disabled"
            else:
                status = "unavailable"
            items.append({
                "id": skill.id,
                "name": skill.name,
                "description": skill.description,
                "version": skill.version,
                "required_tools": list(skill.required_tools),
                "allowed_agents": (
                    list(skill.allowed_agents)
                    if skill.allowed_agents is not None
                    else None
                ),
                "status": status,
                "reason": reason,
            })
        return items

    def list_text(self, *, session_id, agent_id):
        items = self.status_items(session_id=session_id, agent_id=agent_id)
        lines = []
        if items:
            lines.append("**Installed skills:**")
            for item in items:
                suffix = (
                    f" — {item['reason']}"
                    if item["status"] in {"disabled", "unavailable"}
                    else ""
                )
                lines.append(
                    f"- `{item['id']}` [{item['status']}]: "
                    f"{item['description']}{suffix}"
                )
        else:
            lines.append("No valid skills are installed.")
        if self.registry.issues:
            lines.append("**Rejected skills:**")
            lines.extend(
                f"- `{issue.source}`: {issue.error}"
                for issue in self.registry.issues
            )
        return "\n".join(lines)

    def show_text(self, skill_id, *, session_id, agent_id):
        skill = self.registry.get(skill_id)
        if skill is None:
            return f"Skill '{str(skill_id or '').strip()}' was not found."
        item = next(
            item for item in self.status_items(
                session_id=session_id,
                agent_id=agent_id,
            )
            if item["id"] == skill.id
        )
        required = ", ".join(skill.required_tools) or "none"
        agents = (
            ", ".join(skill.allowed_agents)
            if skill.allowed_agents is not None
            else "all"
        )
        return (
            f"**Skill:** `{skill.id}` — {skill.name}\n"
            f"Status: {item['status']} ({item['reason']})\n"
            f"Version: {skill.version}\n"
            f"Description: {skill.description}\n"
            f"Required tools: {required}\n"
            f"Allowed agents: {agents}\n"
            f"Instruction size: {len(skill.instructions.encode('utf-8'))} bytes"
        )

    def reload(self):
        self.registry.reload()
        with self._lock:
            stale_sessions = [
                session_id
                for session_id, skill_id in self._active_by_session.items()
                if self.registry.get(skill_id) is None
                or not self.registry.get(skill_id).enabled
            ]
            for session_id in stale_sessions:
                self._active_by_session.pop(session_id, None)
        return len(stale_sessions)

    def refresh_from_settings(self):
        self.registry.refresh_from_settings()
        with self._lock:
            stale_sessions = [
                session_id
                for session_id, skill_id in self._active_by_session.items()
                if self.registry.get(skill_id) is None
                or not self.registry.get(skill_id).enabled
            ]
            for session_id in stale_sessions:
                self._active_by_session.pop(session_id, None)

    def handle_command(self, command, *, session_id, agent_id):
        raw = str(command or "").strip()
        lowered = raw.lower()
        if lowered == "list skills":
            return self.list_text(session_id=session_id, agent_id=agent_id)
        if lowered == "reload skills":
            cleared = self.reload()
            return (
                f"Reloaded {len(self.registry.skills)} valid skills; "
                f"{len(self.registry.issues)} rejected"
                + (f"; {cleared} stale activations cleared." if cleared else ".")
            )
        if lowered in {"deactivate skill", "disable skill"}:
            return self.deactivate(session_id)[1]
        if lowered == "use skill":
            return "Usage: use skill <skill_id>"
        if lowered.startswith("use skill "):
            skill_id = raw[len("use skill "):].strip().lower()
            return self.activate(
                skill_id,
                session_id=session_id,
                agent_id=agent_id,
            )[1]
        if lowered == "show skill":
            return "Usage: show skill <skill_id>"
        if lowered.startswith("show skill "):
            skill_id = raw[len("show skill "):].strip().lower()
            return self.show_text(
                skill_id,
                session_id=session_id,
                agent_id=agent_id,
            )
        return None
