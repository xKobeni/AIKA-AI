import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

from brain.agent_loop import AgentLoop
from brain.decision_engine import DecisionEngine
from brain.tool_intent_resolver import DeterministicToolIntentResolver
from handlers.response_finalizer import EMPTY_RESPONSE_FALLBACK
from models.actions import Action
from models.tool_request import ToolRequest
from tools.folder_tool import FolderTool
from tools.path_security import (
    resolve_known_user_folder,
    resolve_user_scoped_path,
)
from tools.tool_manager import ToolManager
from tools.web_search_tool import WebSearchTool


def _loop_with_tool(tool, *, max_iterations=2):
    manager = ToolManager()
    manager._audit_log = Mock()
    manager.register_tool(tool)
    llm = Mock()
    llm._uses_configured_client = True
    loop = AgentLoop(
        decision_engine=Mock(),
        router=Mock(),
        llm=llm,
        tool_manager=manager,
        llm_tool_router=object(),
    )
    loop.max_iterations = max_iterations
    return loop, llm


def test_exact_downloads_question_routes_to_read_only_folder_listing():
    request = DeterministicToolIntentResolver().resolve(
        "can you tell me what are the files in the download folder"
    )

    assert request == ToolRequest("folder", {"path": "downloads"})


def test_downloads_known_folder_uses_windows_registry_value(tmp_path):
    downloads = tmp_path / "Downloads"
    downloads.mkdir()

    class FakeKey:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

    fake_winreg = SimpleNamespace(
        HKEY_CURRENT_USER=object(),
        OpenKey=Mock(return_value=FakeKey()),
        QueryValueEx=Mock(return_value=(str(downloads), 0)),
    )
    with patch.dict(sys.modules, {"winreg": fake_winreg}):
        resolved = resolve_known_user_folder("download")

    assert resolved == downloads.resolve()
    fake_winreg.QueryValueEx.assert_called_once_with(
        fake_winreg.OpenKey.return_value,
        "{374DE290-123F-4565-9164-39C4925E467B}",
    )


def test_folder_tool_lists_downloads_root_without_expanding_file_scope(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    downloads = tmp_path / "Downloads"
    downloads.mkdir()
    (downloads / "Movies").mkdir()
    (downloads / "trailer.mp4").write_bytes(b"1234")
    (downloads / ".private.txt").write_text("hidden", encoding="utf-8")

    with patch(
        "tools.folder_tool.resolve_known_user_folder",
        return_value=downloads,
    ):
        result = FolderTool().execute(path="downloads")

    assert result["success"] is True
    assert result["path"] == str(downloads.resolve())
    assert result["folders"] == ["Movies/"]
    assert result["files"] == ["trailer.mp4 (4 B)"]
    assert ".private.txt" not in str(result)

    with patch(
        "tools.folder_tool.resolve_known_user_folder",
        return_value=downloads,
    ):
        hidden = FolderTool().execute(path="downloads", show_hidden=True)
        searched = FolderTool().execute(path="downloads", find="Movies")
    assert hidden == {
        "success": False,
        "error": "Downloads access is limited to a non-hidden root listing",
    }
    assert searched == hidden

    root, target = resolve_user_scoped_path(
        workspace, downloads / "trailer.mp4"
    )
    assert root == workspace.resolve()
    assert target is None


def test_stable_ai_machine_learning_question_never_routes_to_memory():
    classifier = Mock()
    classifier.classify.return_value = {
        "action": Action.USE_TOOL,
        "tool_name": "memory_search",
    }
    engine = DecisionEngine(intent_classifier=classifier)

    action = engine.decide(
        "hmm can you tell me whats the difference between ai and machine learning"
    )

    assert action == Action.CHAT
    classifier.classify.assert_not_called()


def test_contextual_research_followup_uses_previous_user_question():
    resolver = DeterministicToolIntentResolver()

    request = resolver.resolve_followup(
        "i mean can you research about that",
        "hmm can you tell me whats the difference between ai and machine learning",
    )

    assert request == ToolRequest(
        "web_search",
        {
            "query": (
                "can you tell me whats the difference between ai and machine learning"
            )
        },
    )
    assert resolver.resolve_followup(
        "tell me more about that",
        "difference between ai and machine learning",
    ) is None


def test_brain_resolves_contextual_research_from_current_session_only():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = "aika"
    brain.current_session = SimpleNamespace(id="session-1")
    brain.tool_intent_resolver = DeterministicToolIntentResolver()
    brain.conversation_repo = Mock()
    brain.conversation_repo.get_by_session.return_value = [
        SimpleNamespace(
            role="user",
            content="what is unrelated",
            session_id="other-session",
        ),
        SimpleNamespace(
            role="user",
            content="what is the difference between AI and machine learning",
            session_id="session-1",
        ),
        SimpleNamespace(role="assistant", content="A mistaken memory answer."),
    ]

    request = brain._resolve_initial_tool_request(
        "i mean can you research about that"
    )

    assert request == ToolRequest(
        "web_search",
        {"query": "what is the difference between AI and machine learning"},
    )
    brain.conversation_repo.get_by_session.assert_called_once_with(
        "session-1", limit=12, agent_id="aika"
    )


def test_bad_streamed_web_synthesis_is_replaced_before_delivery():
    tool = WebSearchTool()
    tool.execute = Mock(return_value={
        "success": True,
        "outcome": "results",
        "results": [
            {
                "title": "The Most Anticipated Movies of 2026",
                "href": "https://example.test/anticipated-2026",
                "body": "A current list of anticipated 2026 films.",
            },
            {
                "title": "2026 Movie Release Schedule",
                "href": "https://example.test/schedule-2026",
                "body": "A release calendar for 2026 movies.",
            },
        ],
    })
    loop, llm = _loop_with_tool(tool)
    llm.chat.return_value = iter([
        {"message": {"content": (
            "I previously attempted a web search. "
            "[Tool Result: web_search] There aren't any movies listed."
        )}},
    ])

    chunks = list(loop.run_stream(
        "so can you search the internet for the new movies this 2026",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "new movies 2026"}
        ),
    ))
    response = "".join(chunks)

    assert len(chunks) == 1
    assert "Here are the web search results" in response
    assert "The Most Anticipated Movies of 2026" in response
    assert "https://example.test/anticipated-2026" in response
    assert "previously attempted" not in response.lower()
    assert "[Tool Result" not in response
    assert "aren't any movies" not in response.lower()
    assert tool.execute.call_count == 1
    assert llm.chat.call_count == 1


def test_initial_llm_response_error_emits_exactly_one_visible_fallback():
    manager = ToolManager()
    manager._audit_log = Mock()
    llm = Mock()
    llm._uses_configured_client = True
    llm.chat.side_effect = RuntimeError("private Ollama response detail")
    loop = AgentLoop(
        decision_engine=Mock(),
        router=Mock(),
        llm=llm,
        tool_manager=manager,
        llm_tool_router=object(),
    )
    loop.max_iterations = 2

    chunks = list(loop.run_stream("i mean can you research about that"))

    assert chunks == [EMPTY_RESPONSE_FALLBACK]
    assert "".join(chunks) == EMPTY_RESPONSE_FALLBACK
    assert "private Ollama response detail" not in "".join(chunks)
    assert loop.last_run_status == "llm_error"
    assert loop.last_error_type == "RuntimeError"
    assert llm.chat.call_count == 1
