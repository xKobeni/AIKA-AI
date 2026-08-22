from types import SimpleNamespace
from unittest.mock import Mock


def test_retrieval_service_applies_candidate_multiplier_only_in_repository():
    from memory.memory_retrieval_service import MemoryRetrievalService

    repo = Mock()
    repo.semantic_search.return_value = []
    embedding = Mock()
    intent_analyzer = Mock()
    service = MemoryRetrievalService(
        repo, embedding, intent_analyzer=intent_analyzer
    )
    service.intent_analyzer.detect_intent.return_value = "general"

    cached = [0.1] * 768
    service.retrieve("query", limit=7, query_embedding=cached)

    embedding.generate_embedding.assert_not_called()
    from config.settings import settings
    repo.semantic_search.assert_called_once_with(
        cached,
        limit=7 * settings.memory_candidate_multiplier,
        agent_id=None,
        candidate_multiplier=1,
    )


def test_context_manager_reuses_embedding_for_memory_and_cross_session_search():
    from brain.context_manager import ContextManager

    memory_repo = Mock()
    conversation_repo = Mock()
    conversation_repo.get_by_session.return_value = []
    conversation_repo.search_across_sessions.return_value = []
    embedding_service = Mock()
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = []
    retrieval_service.profile_builder.build_profile.return_value = ""
    session_repo = Mock()
    session_repo.get_recent_with_summaries.return_value = []
    manager = ContextManager(
        memory_repo,
        conversation_repo,
        embedding_service,
        retrieval_service=retrieval_service,
        session_repo=session_repo,
    )

    cached = [0.2] * 768
    manager.build_context(
        "same request", session_id="session", query_embedding=cached
    )

    embedding_service.generate_embedding.assert_not_called()
    retrieval_service.retrieve.assert_called_once_with(
        "same request", limit=manager.retrieval_limit,
        agent_id=None, query_embedding=cached
    )
    conversation_repo.search_across_sessions.assert_called_once_with(
        cached, current_session_id="session",
        limit=manager.cross_session_count, agent_id=None
    )


def test_complete_prompt_is_bounded_and_preserves_user_request():
    from brain.context_manager import _count_tokens
    from handlers.chat_handler import ChatHandler

    handler = ChatHandler(Mock(), Mock(), Mock(), Mock())
    handler.context_manager.max_context_tokens = 40
    sections = [
        "Persona instructions " * 20,
        "Memory context " * 100,
        "Final instructions",
        "User:\nkeep this request",
    ]

    prompt = handler._budget_prompt(sections)

    assert _count_tokens(prompt) <= 40
    assert "keep this request" in prompt
    assert "Final instructions" in prompt


def test_scannable_files_prune_dependencies_and_obey_bound(tmp_path):
    from tools.path_security import iter_scannable_files

    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "one.py").write_text("one")
    (tmp_path / "src" / "two.py").write_text("two")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "ignored.js").write_text("ignored")

    files = list(iter_scannable_files(tmp_path, max_files=1))

    assert len(files) == 1
    assert "node_modules" not in files[0].parts


def test_file_search_stops_after_configured_result_limit(tmp_path):
    from tools.file_search_tool import FileSearchTool

    for index in range(5):
        (tmp_path / f"match-{index}.txt").write_text("x")
    tool = FileSearchTool()
    tool.max_results = 2

    result = tool.execute("match", root_path=tmp_path)

    assert result["success"] is True
    assert len(result["file_paths"]) == 2


def test_multi_url_crawl_is_bounded_and_preserves_order():
    from tools.web_crawl_tool import WebCrawlTool

    tool = WebCrawlTool()
    tool.max_workers = 2
    tool.max_urls = 2
    tool._crawl = Mock(
        side_effect=lambda url: {
            "success": True, "url": url, "content": url, "title": ""
        }
    )

    result = tool.execute(["https://one", "https://two", "https://three"])

    assert result["success"] is True
    assert result["total"] == 2
    assert [page["url"] for page in result["pages"]] == [
        "https://one", "https://two"
    ]
    assert tool._crawl.call_count == 2


def test_ollama_client_records_exact_model_metrics():
    from llm.ollama_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    import threading
    client._metrics = threading.local()
    client.model = "model"
    client._chat = Mock(return_value={
        "message": {"content": "answer"},
        "prompt_eval_count": 12,
        "eval_count": 4,
        "total_duration": 25_000_000,
    })

    assert client.generate_with_model("prompt") == "answer"
    assert client.get_last_metrics() == {
        "prompt_tokens": 12,
        "response_tokens": 4,
        "response_time_ms": 25,
    }


def test_chat_metrics_prefer_exact_counts_with_fallbacks():
    from handlers.chat_handler import ChatHandler

    llm = Mock()
    llm.get_last_metrics.return_value = {
        "prompt_tokens": 9,
        "response_tokens": 3,
        "response_time_ms": 17,
    }
    handler = ChatHandler(Mock(), llm, Mock(), Mock())

    assert handler._model_metrics("prompt", "answer", 1.0) == {
        "prompt_tokens": 9,
        "response_tokens": 3,
        "response_time_ms": 17,
    }


def test_agent_response_finalization_uses_model_metrics():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    brain.response_finalizer = Mock()
    brain.response_finalizer.finalize.return_value = "metadata"
    brain.llm = Mock()
    brain.llm.get_last_metrics.return_value = {
        "prompt_tokens": 20,
        "response_tokens": 5,
        "response_time_ms": 30,
    }
    brain.current_session = SimpleNamespace(id="session")
    brain.current_agent_id = "agent"
    user = SimpleNamespace(id=7)

    result = brain._finalize_agent_response("answer", user, "model", 1.0)

    assert result == "metadata"
    brain.response_finalizer.finalize.assert_called_once_with(
        "answer", user_conversation_id=7, session_id="session",
        agent_id="agent", model_used="model", response_time_ms=30,
        prompt_tokens=20, response_tokens=5
    )
