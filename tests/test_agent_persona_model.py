import sys
import os
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from agents.agent_profile import AgentProfile
from agents.agent_registry import AgentRegistry, PERSONAS_DIR


class TestAgentRegistrySetModel:

    def test_set_model_updates_profile(self):
        registry = AgentRegistry()
        registry.create_agent("test1", "Test Agent")
        result = registry.set_model("test1", "llama3:8b")
        assert result is True
        profile = registry.get("test1")
        assert profile.model == "llama3:8b"

    def test_set_model_persists(self, tmp_path):
        data_file = str(tmp_path / "agents.json")
        registry = AgentRegistry(data_path=data_file)
        registry.create_agent("test2", "Test Agent")
        registry.set_model("test2", "qwen2.5:3b")
        registry2 = AgentRegistry(data_path=data_file)
        profile = registry2.get("test2")
        assert profile.model == "qwen2.5:3b"

    def test_set_model_nonexistent_agent(self):
        registry = AgentRegistry()
        result = registry.set_model("nonexistent", "model")
        assert result is False


class TestAgentRegistrySetPersona:

    def test_set_persona_updates_profile(self):
        registry = AgentRegistry()
        registry.create_agent("test1", "Test Agent")
        result = registry.set_persona("test1", "/path/to/persona.txt")
        assert result is True
        profile = registry.get("test1")
        assert profile.persona_path == "/path/to/persona.txt"

    def test_set_persona_persists(self, tmp_path):
        data_file = str(tmp_path / "agents.json")
        registry = AgentRegistry(data_path=data_file)
        registry.create_agent("test2", "Test Agent")
        registry.set_persona("test2", "/new/persona.txt")
        registry2 = AgentRegistry(data_path=data_file)
        profile = registry2.get("test2")
        assert profile.persona_path == "/new/persona.txt"

    def test_set_persona_nonexistent_agent(self):
        registry = AgentRegistry()
        result = registry.set_persona("nonexistent", "/path/to/persona.txt")
        assert result is False


class TestPersonaFileWriting:

    def test_write_persona_file(self, tmp_path):
        persona_dir = str(tmp_path / "personas")
        os.makedirs(persona_dir, exist_ok=True)
        persona_path = os.path.join(persona_dir, "test_agent.txt")
        content = "You are a helpful test agent."
        with open(persona_path, "w", encoding="utf-8") as f:
            f.write(content)
        assert os.path.exists(persona_path)
        with open(persona_path, "r", encoding="utf-8") as f:
            assert f.read() == content

    def test_persona_path_resolution(self):
        expected = os.path.join(PERSONAS_DIR, "aika.txt")
        assert expected.endswith("aika.txt")
        assert "personas" in expected
