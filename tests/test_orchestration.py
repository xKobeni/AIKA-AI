import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from brain.shared_context import SharedContext
from brain.agent_message import AgentMessage
from brain.orchestrator import Orchestrator
from agents.agent_profile import AgentProfile


class TestSharedContext:

    def test_set_and_get(self):
        ctx = SharedContext()
        ctx.set("key1", "value1")
        assert ctx.get("key1") == "value1"

    def test_get_default(self):
        ctx = SharedContext()
        assert ctx.get("missing", "default") == "default"

    def test_get_all(self):
        ctx = SharedContext()
        ctx.set("a", 1)
        ctx.set("b", 2)
        assert ctx.get_all() == {"a": 1, "b": 2}

    def test_agent_results_tracking(self):
        ctx = SharedContext()
        ctx.set("result", "data", agent_id="agent_1")
        results = ctx.get_agent_results("agent_1")
        assert len(results) == 1
        assert results[0]["key"] == "result"

    def test_clear(self):
        ctx = SharedContext()
        ctx.set("a", 1)
        ctx.clear()
        assert ctx.get("a") is None


class TestAgentMessage:

    def test_task_creation(self):
        msg = AgentMessage.task("aika", "researcher", "find AI news")
        assert msg.from_agent == "aika"
        assert msg.to_agent == "researcher"
        assert msg.message_type == "task"
        assert msg.payload["task"] == "find AI news"

    def test_result_creation(self):
        msg = AgentMessage.result("researcher", "aika", "found 5 articles")
        assert msg.message_type == "result"
        assert msg.payload["result"] == "found 5 articles"
        assert msg.payload["success"] is True

    def test_handoff_creation(self):
        msg = AgentMessage.handoff("aika", "writer", {"context": "data"})
        assert msg.message_type == "handoff"
        assert msg.payload["context"] == {"context": "data"}

    def test_serialization(self):
        msg = AgentMessage.task("aika", "planner", "plan task")
        d = msg.to_dict()
        restored = AgentMessage.from_dict(d)
        assert restored.from_agent == "aika"
        assert restored.to_agent == "planner"
        assert restored.message_type == "task"


class TestOrchestratorDelegate:

    def test_delegate_calls_agent_loop(self):
        mock_registry = MagicMock()
        mock_registry.get.return_value = AgentProfile(id="target", name="Target")
        mock_loop = MagicMock()
        mock_loop.run.return_value = "research result"

        orch = Orchestrator(mock_registry, mock_loop)
        result = orch.delegate("aika", "find news", "target")

        mock_loop.run.assert_called_once_with("find news", agent_id="target")
        assert result == "research result"

    def test_delegate_stores_in_context(self):
        mock_registry = MagicMock()
        mock_registry.get.return_value = AgentProfile(id="target", name="Target")
        mock_loop = MagicMock()
        mock_loop.run.return_value = "result"

        ctx = SharedContext()
        orch = Orchestrator(mock_registry, mock_loop)
        orch.delegate("aika", "task", "target", shared_context=ctx)

        assert ctx.get("task") == "task"
        assert ctx.get("result") == "result"


class TestOrchestratorChain:

    def test_run_chain_sequential(self):
        mock_registry = MagicMock()
        mock_registry.get.return_value = AgentProfile(id="agent", name="Agent")
        mock_loop = MagicMock()
        mock_loop.run.return_value = "step result"

        orch = Orchestrator(mock_registry, mock_loop)
        result = orch.run_chain(["agent1", "agent2"], "initial task")

        assert mock_loop.run.call_count == 2
        assert result == "step result"

    def test_run_chain_with_invalid_agent(self):
        mock_registry = MagicMock()
        mock_registry.get.return_value = None
        mock_loop = MagicMock()

        orch = Orchestrator(mock_registry, mock_loop)
        result = orch.run_chain(["nonexistent"], "task")

        assert result == ""
        mock_loop.run.assert_not_called()


class TestOrchestratorTeam:

    def test_run_team_multiple_turns(self):
        mock_registry = MagicMock()
        mock_registry.get.return_value = AgentProfile(id="agent", name="Agent")
        mock_loop = MagicMock()
        mock_loop.run.side_effect = ["contribution 1", "contribution 2 [TEAM_DONE]"]

        orch = Orchestrator(mock_registry, mock_loop)
        result = orch.run_team(["agent1"], "team task", max_turns=5)

        assert mock_loop.run.call_count == 2
        assert "contribution 1" in result

    def test_run_team_max_turns(self):
        mock_registry = MagicMock()
        mock_registry.get.return_value = AgentProfile(id="agent", name="Agent")
        mock_loop = MagicMock()
        mock_loop.run.return_value = "ongoing contribution"

        orch = Orchestrator(mock_registry, mock_loop)
        result = orch.run_team(["agent1"], "task", max_turns=2)

        assert mock_loop.run.call_count == 2


class TestDecisionEngineDelegation:

    def test_delegation_detection(self):
        from brain.decision_engine import DecisionEngine
        engine = DecisionEngine()

        assert engine.decide("have the researcher find AI news").value == "delegate"
        assert engine.decide("ask the planner to create a plan").value == "delegate"
        assert engine.decide("delegate to writer format the report").value == "delegate"

    def test_orchestration_detection(self):
        from brain.decision_engine import DecisionEngine
        engine = DecisionEngine()

        assert engine.decide("chain researcher,planner do task").value == "orchestrate"
        assert engine.decide("team researcher,writer complete task").value == "orchestrate"
        assert engine.decide("parallel researcher,planner run search").value == "orchestrate"
