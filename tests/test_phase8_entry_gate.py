import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch


def test_intent_classifier_initializes_and_reuses_cache():
    from brain.intent_classifier import LLMIntentClassifier
    from models.actions import Action

    llm = Mock()
    llm.chat.return_value = {"message": {"content": "CHAT"}}
    classifier = LLMIntentClassifier(llm=llm)

    first = classifier.classify("explain this request")
    second = classifier.classify("explain this request")

    assert first == {"action": Action.CHAT, "tool_name": None}
    assert second == first
    llm.chat.assert_called_once()


def test_deterministic_os_routes_do_not_depend_on_classifier():
    from brain.decision_engine import DecisionEngine
    from models.actions import Action

    classifier = Mock()
    classifier.classify.return_value = {"action": Action.CHAT, "tool_name": None}
    engine = DecisionEngine(intent_classifier=classifier)

    assert engine.decide("open spotify") == Action.USE_TOOL
    assert engine.decide("show files") == Action.USE_TOOL
    classifier.classify.assert_not_called()


def test_ollama_model_listing_supports_current_sdk_objects():
    from llm.ollama_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    client.client = Mock()
    client.client.list.return_value = {
        "models": [
            SimpleNamespace(model="current-model:latest"),
            {"name": "legacy-model:latest"},
        ]
    }

    assert client.list_models() == [
        "current-model:latest",
        "legacy-model:latest",
    ]


def test_file_delete_never_deletes_workspace_root(tmp_path):
    from tools.file_delete_tool import FileDeleteTool

    marker = tmp_path / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with patch("tools.file_delete_tool.settings") as mock_settings:
        mock_settings.file_delete_enabled = True
        mock_settings.protected_paths = []
        result = FileDeleteTool().execute(
            ".", recursive=True, root_path=str(tmp_path)
        )

    assert result["success"] is False
    assert "workspace root" in result["error"]
    assert marker.read_text(encoding="utf-8") == "keep"


def test_redaction_covers_namespaced_credentials_and_errors(tmp_path):
    from tools.tool_manager import ToolManager, _redact_sensitive

    assert _redact_sensitive({"github_token": "private-value"}) == {
        "github_token": "[REDACTED]"
    }

    log_path = tmp_path / "audit.log"
    manager = ToolManager()
    with patch("config.settings.settings") as mock_settings:
        mock_settings.audit_log_enabled = True
        mock_settings.audit_log_path = str(log_path)
        manager._audit_log(
            "example",
            {},
            {"success": False, "error": "password=private-value"},
        )

    content = log_path.read_text(encoding="utf-8")
    assert "private-value" not in content
    assert "[REDACTED]" in content


def test_test_runner_is_high_permission_and_contained(tmp_path):
    from tools.test_runner_tool import TestRunnerTool
    from tools.tool_permission import ToolPermission

    root = tmp_path / "workspace"
    outside = tmp_path / "outside"
    root.mkdir()
    outside.mkdir()
    tool = TestRunnerTool()

    with patch("tools.test_runner_tool.subprocess.run") as run:
        denied = tool.execute(str(outside), root_path=str(root))

    assert tool.permission == ToolPermission.HIGH
    assert denied["success"] is False
    assert "outside workspace" in denied["error"]
    run.assert_not_called()


def test_test_runner_uses_current_python_and_workspace(tmp_path):
    from tools.test_runner_tool import TestRunnerTool

    test_file = tmp_path / "test_example.py"
    test_file.write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    completed = Mock(returncode=0, stdout="ok", stderr="")
    with patch(
        "tools.test_runner_tool.subprocess.run", return_value=completed
    ) as run:
        result = TestRunnerTool().execute(
            "test_example.py", verbose=False, root_path=str(tmp_path)
        )

    assert result["success"] is True
    run.assert_called_once_with(
        [sys.executable, "-m", "pytest", str(test_file.resolve()), "--tb=short"],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=str(tmp_path.resolve()),
    )
