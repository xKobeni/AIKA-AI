import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock


def _write_skill(
    root,
    skill_id="research_assistant",
    *,
    instructions="Research carefully and cite the supplied sources.",
    required_tools=None,
    allowed_agents=None,
    enabled=True,
    manifest_updates=None,
):
    directory = root / skill_id
    directory.mkdir(parents=True)
    manifest = {
        "id": skill_id,
        "name": skill_id.replace("_", " ").title(),
        "description": "A test skill.",
        "version": "1.0",
        "required_tools": list(required_tools or []),
        "enabled": enabled,
    }
    if allowed_agents is not None:
        manifest["allowed_agents"] = list(allowed_agents)
    if manifest_updates:
        manifest.update(manifest_updates)
    (directory / "skill.json").write_text(
        json.dumps(manifest),
        encoding="utf-8",
    )
    (directory / "SKILL.md").write_text(
        instructions,
        encoding="utf-8",
    )
    return directory


def _manager(root, *, registered=(), allowed_tools=None):
    from skills.manager import SkillManager
    from skills.registry import SkillRegistry

    tool_manager = SimpleNamespace(
        tools={name: Mock() for name in registered}
    )
    profile = SimpleNamespace(allowed_tools=allowed_tools)
    agent_registry = SimpleNamespace(
        get=lambda agent_id: profile if agent_id == "aika" else None
    )
    registry = SkillRegistry(root)
    return SkillManager(
        registry,
        tool_manager=tool_manager,
        agent_registry=agent_registry,
    )


def test_valid_skill_is_discovered_and_activated_for_one_session(tmp_path):
    _write_skill(
        tmp_path,
        required_tools=["web_search"],
        allowed_agents=["aika"],
    )
    manager = _manager(
        tmp_path,
        registered=["web_search", "calculator"],
        allowed_tools=["web_search"],
    )

    success, message = manager.activate(
        "research_assistant",
        session_id="session-a",
        agent_id="aika",
    )

    assert success is True
    assert "Activated skill" in message
    assert manager.active_skill(
        session_id="session-a", agent_id="aika"
    ).id == "research_assistant"
    assert manager.active_skill(
        session_id="session-b", agent_id="aika"
    ) is None
    prompt = manager.prompt_for(session_id="session-a", agent_id="aika")
    assert "=== ACTIVE SKILL:" in prompt
    assert "permissions prevail" in prompt
    assert "Research carefully" in prompt


def test_new_session_does_not_inherit_and_deactivation_is_session_scoped(tmp_path):
    _write_skill(tmp_path)
    manager = _manager(tmp_path)
    assert manager.activate(
        "research_assistant", session_id="old", agent_id="aika"
    )[0]

    assert manager.active_skill(session_id="new", agent_id="aika") is None
    assert manager.active_skill(session_id="old", agent_id="aika") is not None
    assert manager.deactivate("new")[0] is False
    assert manager.deactivate("old")[0] is True
    assert manager.active_skill(session_id="old", agent_id="aika") is None


def test_missing_and_agent_denied_tools_fail_closed(tmp_path):
    _write_skill(tmp_path, required_tools=["web_search", "web_crawl"])
    missing = _manager(
        tmp_path,
        registered=["web_search"],
        allowed_tools=["web_search"],
    )
    success, message = missing.activate(
        "research_assistant", session_id="s", agent_id="aika"
    )
    assert success is False
    assert "missing required tools: web_crawl" in message

    denied = _manager(
        tmp_path,
        registered=["web_search", "web_crawl"],
        allowed_tools=["web_search"],
    )
    success, message = denied.activate(
        "research_assistant", session_id="s", agent_id="aika"
    )
    assert success is False
    assert "agent cannot use required tools: web_crawl" in message


def test_disabled_tool_setting_prevents_activation(tmp_path, monkeypatch):
    from config.settings import settings

    _write_skill(tmp_path, required_tools=["shell"])
    manager = _manager(
        tmp_path,
        registered=["shell"],
        allowed_tools=["shell"],
    )
    monkeypatch.setattr(settings, "shell_enabled", False)

    success, message = manager.activate(
        "research_assistant", session_id="s", agent_id="aika"
    )

    assert success is False
    assert "disabled required tools: shell" in message


def test_agent_allowlist_and_disabled_manifest_are_reported(tmp_path):
    _write_skill(
        tmp_path,
        "planner_only",
        allowed_agents=["planner"],
    )
    _write_skill(tmp_path, "turned_off", enabled=False)
    manager = _manager(tmp_path)

    items = {item["id"]: item for item in manager.status_items(
        session_id="s", agent_id="aika"
    )}

    assert items["planner_only"]["status"] == "unavailable"
    assert "not allowed for agent" in items["planner_only"]["reason"]
    assert items["turned_off"]["status"] == "disabled"


def test_malformed_skill_does_not_block_valid_skill(tmp_path):
    _write_skill(tmp_path, "valid_skill")
    broken = tmp_path / "broken_skill"
    broken.mkdir()
    (broken / "skill.json").write_text("{bad json", encoding="utf-8")
    (broken / "SKILL.md").write_text("instructions", encoding="utf-8")

    manager = _manager(tmp_path)

    assert [skill.id for skill in manager.registry.get_all()] == ["valid_skill"]
    assert len(manager.registry.issues) == 1
    assert manager.registry.issues[0].source == "broken_skill"
    listing = manager.list_text(session_id="s", agent_id="aika")
    assert "valid_skill" in listing
    assert "broken_skill" in listing


def test_manifest_validation_rejects_unknown_fields_and_directory_mismatch(tmp_path):
    _write_skill(
        tmp_path,
        "wrong_directory",
        manifest_updates={"id": "different_id", "surprise": True},
    )

    manager = _manager(tmp_path)

    assert manager.registry.get_all() == []
    assert "unknown fields: surprise" in manager.registry.issues[0].error


def test_oversized_instructions_are_rejected(tmp_path):
    from skills.registry import SkillRegistry

    _write_skill(tmp_path, instructions="x" * 65)
    registry = SkillRegistry(tmp_path, max_instruction_bytes=64)

    assert registry.get_all() == []
    assert "SKILL.md exceeds 64 bytes" in registry.issues[0].error


def test_symbolic_instruction_file_is_rejected_without_following_it(
    tmp_path, monkeypatch
):
    from skills.registry import SkillRegistry

    _write_skill(tmp_path)
    original = Path.is_symlink
    monkeypatch.setattr(
        Path,
        "is_symlink",
        lambda path: path.name == "SKILL.md" or original(path),
    )

    registry = SkillRegistry(tmp_path)

    assert registry.get_all() == []
    assert "SKILL.md must not be a symbolic link" in registry.issues[0].error


def test_explicit_commands_do_not_match_ordinary_chat(tmp_path):
    _write_skill(tmp_path)
    manager = _manager(tmp_path)

    assert manager.handle_command(
        "I use skills when I work",
        session_id="s",
        agent_id="aika",
    ) is None
    assert "research_assistant" in manager.handle_command(
        "list skills", session_id="s", agent_id="aika"
    )
    assert "Activated skill" in manager.handle_command(
        "use skill research_assistant",
        session_id="s",
        agent_id="aika",
    )
    assert "Status: active" in manager.handle_command(
        "show skill research_assistant",
        session_id="s",
        agent_id="aika",
    )
    assert "Deactivated skill" in manager.handle_command(
        "deactivate skill",
        session_id="s",
        agent_id="aika",
    )


def test_brain_routes_use_skill_before_use_agent(tmp_path):
    from brain.brain import AikaBrain

    _write_skill(tmp_path)
    brain = AikaBrain.__new__(AikaBrain)
    brain.skill_manager = _manager(tmp_path)
    brain.current_session = SimpleNamespace(id="session-1")
    brain.current_agent_id = "aika"

    result = brain.process("use skill research_assistant")

    assert "Activated skill" in result


def test_reload_clears_an_activation_when_skill_becomes_disabled(tmp_path):
    directory = _write_skill(tmp_path)
    manager = _manager(tmp_path)
    assert manager.activate(
        "research_assistant", session_id="s", agent_id="aika"
    )[0]
    manifest_path = directory / "skill.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["enabled"] = False
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    cleared = manager.reload()

    assert cleared == 1
    assert manager.active_skill(session_id="s", agent_id="aika") is None


def test_chat_prompt_includes_budgeted_skill_and_preserves_user_request(tmp_path):
    from brain.prompt_budgeter import count_tokens
    from brain.request_context import RequestContext
    from handlers.chat_handler import ChatHandler

    _write_skill(tmp_path, instructions="SKILL-DIRECTIVE " * 100)
    manager = _manager(tmp_path)
    manager.activate("research_assistant", session_id="s", agent_id="aika")
    context_manager = Mock(max_context_tokens=220)
    handler = ChatHandler(
        Mock(), Mock(), Mock(), context_manager,
        skill_manager=manager,
        session_id="s",
    )
    request_context = RequestContext(
        user_message="keep this exact request",
        agent_id="aika",
        session_id="s",
        persona="AIKA",
        current_time="21:00",
        current_date="Monday, August 24, 2026",
        memory_context="",
        conversation_context="",
        cross_session_context="",
        allowed_tools=(),
    )
    sections = handler._assemble_prompt_sections(
        request_context,
        "keep this exact request",
        "",
        handler._active_skill_prompt("aika"),
    )

    prompt = handler._budget_prompt(sections)

    assert count_tokens(prompt) <= 220
    assert "=== ACTIVE SKILL:" in prompt
    assert "SKILL-DIRECTIVE" in prompt
    assert "keep this exact request" in prompt
    assert "IDENTITY AND GROUNDING RULES" in prompt


def test_agent_prompt_includes_active_skill_for_request_session(tmp_path):
    from brain.agent_context import AgentContext
    from brain.agent_loop import AgentLoop
    from brain.request_context import RequestContext

    _write_skill(tmp_path, instructions="Use the phase-nine procedure.")
    manager = _manager(tmp_path)
    manager.activate("research_assistant", session_id="s", agent_id="aika")
    tool_manager = Mock()
    tool_manager.tools = {}
    tool_manager.get_schemas_json.return_value = "[]"
    loop = AgentLoop(
        Mock(), Mock(), Mock(),
        tool_manager=tool_manager,
        skill_manager=manager,
    )
    request_context = RequestContext(
        user_message="do the task",
        agent_id="aika",
        session_id="s",
        persona="AIKA",
        current_time="21:00",
        current_date="Monday, August 24, 2026",
        memory_context="",
        conversation_context="",
        cross_session_context="",
        allowed_tools=(),
    )

    parts = loop._build_system_prompt_parts(
        AgentContext("do the task"),
        agent_id="aika",
        request_context=request_context,
    )

    assert any("Use the phase-nine procedure." in part for part in parts)


def test_capabilities_distinguish_tools_skills_and_active_skill(tmp_path):
    from tools.capabilities_tool import CapabilitiesTool

    _write_skill(tmp_path, required_tools=["calculator"])
    _write_skill(tmp_path, "missing_tool", required_tools=["web_search"])
    manager = _manager(
        tmp_path,
        registered=["calculator"],
        allowed_tools=["calculator"],
    )
    manager.activate("research_assistant", session_id="s", agent_id="aika")
    calculator = SimpleNamespace(
        description="Performs calculations",
        category=SimpleNamespace(value="productivity"),
        permission=SimpleNamespace(value="low"),
    )
    tool = CapabilitiesTool(
        SimpleNamespace(tools={"calculator": calculator}),
        agent_registry=SimpleNamespace(
            get=lambda _agent_id: SimpleNamespace(
                allowed_tools=["calculator"]
            )
        ),
        agent_id_provider=lambda: "aika",
        skill_manager=manager,
        session_id_provider=lambda: "s",
    )

    result = tool.execute()

    assert result["active_skill"] == "research_assistant"
    statuses = {item["id"]: item["status"] for item in result["skills"]}
    assert statuses["research_assistant"] == "active"
    assert statuses["missing_tool"] == "unavailable"
    assert "Installed skills:" in result["text"]
    assert "Active skill: research_assistant" in result["text"]
    assert "missing required tools: web_search" in result["text"]
