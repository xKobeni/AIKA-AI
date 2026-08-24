from types import SimpleNamespace
from concurrent.futures import Future
from contextlib import contextmanager
from threading import BoundedSemaphore
from unittest.mock import MagicMock, Mock, patch


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


def test_token_estimate_is_conservative_for_dense_nonword_content():
    from brain.context_manager import _count_tokens

    dense = "x" * 400

    assert _count_tokens(dense) >= 101


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


def test_memory_retrieval_batches_changed_profile_scores():
    from memory.memory_retrieval_service import MemoryRetrievalService

    memories = [
        SimpleNamespace(
            id=1, category="project", access_count=5,
            importance=8, profile_score=0,
        ),
        SimpleNamespace(
            id=2, category="fact", access_count=0,
            importance=5, profile_score=0,
        ),
    ]
    repo = Mock()
    repo.semantic_search.return_value = memories
    ranker = Mock()
    ranker.filter_by_intent.side_effect = lambda items, _intent: items
    ranker.rank.side_effect = lambda items, _intent: items
    ranker.apply_diversity.side_effect = lambda items: items
    intent_analyzer = Mock()
    intent_analyzer.detect_intent.return_value = "general"
    service = MemoryRetrievalService(
        repo,
        Mock(),
        intent_analyzer=intent_analyzer,
        ranker=ranker,
    )

    result = service.retrieve(
        "project status", limit=2, query_embedding=[0.1] * 768
    )

    assert result == memories
    repo.batch_update_profile_scores.assert_called_once_with({1: 7})
    repo.update_profile_score.assert_not_called()


def test_context_manager_batches_memory_access_tracking():
    from brain.context_manager import ContextManager

    memory_repo = Mock()
    conversation_repo = Mock()
    conversation_repo.get_by_session.return_value = []
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = [
        SimpleNamespace(id=3, category="fact", content="one"),
        SimpleNamespace(id=4, category="project", content="two"),
    ]
    retrieval_service.profile_builder.build_profile.return_value = ""
    manager = ContextManager(
        memory_repo,
        conversation_repo,
        Mock(),
        retrieval_service=retrieval_service,
    )

    manager.build_context(
        "query", session_id="session", query_embedding=[0.2] * 768
    )

    memory_repo.batch_update_access.assert_called_once_with([3, 4])
    memory_repo.update_access.assert_not_called()


def test_profile_builder_uses_database_bounded_selection():
    from memory.memory_profile import MemoryProfileBuilder

    repo = Mock()
    repo.get_top_profile_memories.return_value = [
        SimpleNamespace(category="project", content="AIKA"),
        SimpleNamespace(category="goal", content="Ship performance fixes"),
    ]
    builder = MemoryProfileBuilder(repo)

    profile = builder.build_profile(max_per_category=2, agent_id="aika")

    assert "AIKA" in profile
    assert "Ship performance fixes" in profile
    repo.get_top_profile_memories.assert_called_once_with(
        builder.PREFERRED_CATEGORIES,
        max_per_category=2,
        agent_id="aika",
    )
    repo.get_by_categories.assert_not_called()


def test_batch_access_update_uses_one_query():
    from database.models import Memory
    from repositories.memory_repository import MemoryRepository

    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value.update.return_value = 2

    @contextmanager
    def fake_session():
        yield db

    with patch("repositories.memory_repository.db_session", fake_session):
        updated = MemoryRepository().batch_update_access([4, 4, 5])

    assert updated == 2
    db.query.assert_called_once_with(Memory)
    query.filter.return_value.update.assert_called_once()


def test_profile_query_limits_each_category_in_sql():
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.orm import Session
    from repositories.memory_repository import MemoryRepository

    query = MemoryRepository._top_profile_query(
        Session(),
        ["project", "goal"],
        2,
        agent_id="aika",
    )
    sql = str(query.statement.compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))

    assert "row_number() OVER" in sql
    assert "PARTITION BY memories.category" in sql
    assert "category_rank <= 2" in sql
    assert "memories.agent_id = 'aika'" in sql


def test_batch_profile_score_update_uses_one_session():
    from database.models import Memory
    from repositories.memory_repository import MemoryRepository

    db = MagicMock()

    @contextmanager
    def fake_session():
        yield db

    with patch("repositories.memory_repository.db_session", fake_session):
        updated = MemoryRepository().batch_update_profile_scores({1: 4, 2: 7})

    assert updated == 2
    db.bulk_update_mappings.assert_called_once_with(
        Memory,
        [
            {"id": 1, "profile_score": 4},
            {"id": 2, "profile_score": 7},
        ],
    )


def test_semantic_conversation_results_keep_nearest_first_order():
    from repositories.conversation_repository import ConversationRepository

    nearest = SimpleNamespace(id=1)
    farther = SimpleNamespace(id=2)
    db = MagicMock()
    query = db.query.return_value
    query.filter.return_value = query
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = [nearest, farther]

    @contextmanager
    def fake_session():
        yield db

    with patch("repositories.conversation_repository.db_session", fake_session):
        result = ConversationRepository().semantic_search(
            [0.1] * 768, limit=2
        )

    assert result == [nearest, farther]


def test_session_listing_applies_limit_in_database_query():
    from repositories.session_repository import SessionRepository

    db = MagicMock()
    query = db.query.return_value
    query.order_by.return_value = query
    query.limit.return_value = query
    query.all.return_value = []

    @contextmanager
    def fake_session():
        yield db

    with patch("repositories.session_repository.db_session", fake_session):
        SessionRepository().get_all_sessions(limit=25)

    query.limit.assert_called_once_with(25)


def test_background_submission_rejects_work_when_capacity_is_full():
    from brain.brain import AikaBrain

    first = Future()
    second = Future()
    brain = AikaBrain.__new__(AikaBrain)
    brain._closed = False
    brain._executor = Mock()
    brain._executor.submit.side_effect = [first, second]
    brain._background_capacity = BoundedSemaphore(1)

    assert brain._submit_background("first", Mock()) is True
    assert brain._submit_background("overflow", Mock()) is False
    assert brain._executor.submit.call_count == 1

    first.set_result(None)
    assert brain._submit_background("second", Mock()) is True
    second.set_result(None)
    assert brain._executor.submit.call_count == 2


def test_disabled_streaming_uses_synchronous_brain_path():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    brain.process = Mock(return_value="complete response")

    with patch("brain.brain.settings.streaming_enabled", False):
        chunks = list(brain.process_stream("hello"))

    assert chunks == ["complete response"]
    brain.process.assert_called_once_with("hello")


def test_orchestrator_refreshes_worker_and_team_limits():
    from brain.orchestrator import Orchestrator

    with patch("brain.orchestrator.settings") as mock_settings:
        mock_settings.orchestrator_max_workers = 2
        mock_settings.orchestration_max_team_turns = 6
        orchestrator = Orchestrator(Mock(), Mock())
        assert orchestrator.max_workers == 2
        assert orchestrator.max_team_turns == 6

        mock_settings.orchestrator_max_workers = 3
        mock_settings.orchestration_max_team_turns = 8
        orchestrator.refresh_from_settings()

    assert orchestrator.max_workers == 3
    assert orchestrator.max_team_turns == 8
