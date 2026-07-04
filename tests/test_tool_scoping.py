import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from tools.tool_manager import ToolManager
from brain.tool_call_parser import ToolCallParser
from agents.agent_profile import AgentProfile
from agents.agent_registry import AgentRegistry


class MockTool:

    def __init__(self, name):
        self.name = name
        self.category = "test"

    def execute(self, **kwargs):
        return {"success": True, "tool": self.name}

    def get_schema(self):
        return {"name": self.name, "parameters": {}}


class TestToolManagerExecuteTool:

    def test_execute_tool_no_restriction(self):
        tm = ToolManager()
        tm.register_tool(MockTool("calculator"))
        result = tm.execute_tool("calculator", expression="2+2")
        assert result["success"] is True
        assert result["tool"] == "calculator"

    def test_execute_tool_allowed_tool_passes(self):
        tm = ToolManager()
        tm.register_tool(MockTool("calculator"))
        tm.register_tool(MockTool("shell"))
        result = tm.execute_tool(
            "calculator",
            allowed_tool_names={"calculator", "shell"},
            expression="2+2"
        )
        assert result["success"] is True

    def test_execute_tool_disallowed_tool_blocked(self):
        tm = ToolManager()
        tm.register_tool(MockTool("calculator"))
        tm.register_tool(MockTool("shell"))
        result = tm.execute_tool(
            "shell",
            allowed_tool_names={"calculator"},
            command="dir"
        )
        assert result["success"] is False
        assert "not available" in result["error"]

    def test_execute_tool_unknown_tool_still_fails(self):
        tm = ToolManager()
        tm.register_tool(MockTool("calculator"))
        result = tm.execute_tool(
            "nonexistent",
            allowed_tool_names={"calculator"}
        )
        assert result["success"] is False
        assert "Unknown tool" in result["error"]

    def test_execute_tool_allowed_none_means_all(self):
        tm = ToolManager()
        tm.register_tool(MockTool("calculator"))
        result = tm.execute_tool("calculator", allowed_tool_names=None)
        assert result["success"] is True


class TestToolCallParserScoping:

    def test_parser_rejects_disallowed_tool(self):
        parser = ToolCallParser(tool_names={"calculator", "shell"})
        result = parser.parse('{"tool": "web_search", "parameters": {}}')
        assert result is None

    def test_parser_allows_valid_tool(self):
        parser = ToolCallParser(tool_names={"calculator", "shell"})
        result = parser.parse('{"tool": "calculator", "parameters": {"expression": "2+2"}}')
        assert result is not None
        assert result["tool"] == "calculator"

    def test_parser_no_restriction_allows_all(self):
        parser = ToolCallParser(tool_names=None)
        result = parser.parse('{"tool": "anything", "parameters": {}}')
        assert result is not None


class TestAgentProfileAllowedTools:

    def test_profile_no_restriction(self):
        profile = AgentProfile(id="a1", name="Test")
        assert profile.allowed_tools is None

    def test_profile_with_tools(self):
        profile = AgentProfile(
            id="a1", name="Test",
            allowed_tools=["calculator", "shell"]
        )
        assert profile.allowed_tools == ["calculator", "shell"]

    def test_profile_serialization(self):
        profile = AgentProfile(
            id="a1", name="Test",
            allowed_tools=["calculator"]
        )
        d = profile.to_dict()
        restored = AgentProfile.from_dict(d)
        assert restored.allowed_tools == ["calculator"]

    def test_profile_serialization_none_tools(self):
        profile = AgentProfile(id="a1", name="Test")
        d = profile.to_dict()
        restored = AgentProfile.from_dict(d)
        assert restored.allowed_tools is None


class TestAgentRegistryTools:

    def test_create_agent_with_tools(self, tmp_path):
        data_file = str(tmp_path / "agents.json")
        registry = AgentRegistry(data_path=data_file)
        profile = registry.create_agent("test_scoping_1", "Test Agent", allowed_tools=["calculator"])
        assert profile is not None
        assert profile.allowed_tools == ["calculator"]
        loaded = registry.get("test_scoping_1")
        assert loaded.allowed_tools == ["calculator"]

    def test_create_agent_without_tools(self, tmp_path):
        data_file = str(tmp_path / "agents.json")
        registry = AgentRegistry(data_path=data_file)
        profile = registry.create_agent("test_scoping_2", "Test Agent")
        assert profile is not None
        assert profile.allowed_tools is None
