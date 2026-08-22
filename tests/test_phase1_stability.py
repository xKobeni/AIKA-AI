from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from brain.brain import AikaBrain
from brain.context_manager import ContextManager
from database.models import Conversation
from handlers.chat_handler import ChatHandler
from handlers.memory_handler import MemoryHandler
from memory.memory_retrieval_service import MemoryRetrievalService
from models.actions import Action
from repositories.conversation_repository import ConversationRepository


class RecordingQuery:
    def __init__(self, scalar_value=None):
        self.operations = []
        self.scalar_value = scalar_value
        self.deleted = False

    def filter(self, *conditions):
        if any(name == "limit" for name, _ in self.operations):
            raise AssertionError("filter called after limit")
        self.operations.append(("filter", conditions))
        return self

    def order_by(self, *values):
        self.operations.append(("order_by", values))
        return self

    def offset(self, value):
        self.operations.append(("offset", value))
        return self

    def limit(self, value):
        self.operations.append(("limit", value))
        return self

    def all(self):
        self.operations.append(("all", None))
        return []

    def scalar(self):
        self.operations.append(("scalar", None))
        return self.scalar_value

    def delete(self, synchronize_session=False):
        self.operations.append(("delete", synchronize_session))
        self.deleted = True


class RecordingDb:
    def __init__(self, queries=None):
        self.queries = list(queries or [])
        self.created_queries = []

    def query(self, *entities):
        query = self.queries.pop(0) if self.queries else RecordingQuery()
        self.created_queries.append((entities, query))
        return query


def fake_db_session(db):
    @contextmanager
    def manager():
        yield db
    return manager


def test_agent_filter_is_applied_before_semantic_search_limit():
    db = RecordingDb()
    repo = ConversationRepository()

    with patch(
        "repositories.conversation_repository.db_session",
        fake_db_session(db),
    ):
        assert repo.semantic_search([0.1] * 768, agent_id="agent_a") == []

    operations = [name for name, _ in db.created_queries[0][1].operations]
    assert operations[-2:] == ["limit", "all"]
    assert operations.count("filter") == 2


def test_agent_filter_is_applied_before_cross_session_limit():
    db = RecordingDb()
    repo = ConversationRepository()

    with patch(
        "repositories.conversation_repository.db_session",
        fake_db_session(db),
    ):
        assert repo.search_across_sessions(
            [0.1] * 768,
            current_session_id="current",
            agent_id="agent_a",
        ) == []

    operations = [name for name, _ in db.created_queries[0][1].operations]
    assert operations[-2:] == ["limit", "all"]
    assert operations.count("filter") == 3


def test_trim_scopes_count_boundary_and_delete_to_agent():
    count_query = RecordingQuery(scalar_value=5)
    keep_query = RecordingQuery(scalar_value=4)
    delete_query = RecordingQuery()
    db = RecordingDb([count_query, keep_query, delete_query])
    repo = ConversationRepository()

    with patch(
        "repositories.conversation_repository.db_session",
        fake_db_session(db),
    ):
        repo.trim(max_count=3, agent_id="agent_a")

    assert count_query.operations[0][0] == "filter"
    assert keep_query.operations[0][0] == "filter"
    assert [name for name, _ in delete_query.operations].count("filter") == 2
    assert delete_query.deleted is True

    for query in (count_query, keep_query, delete_query):
        first_filter = next(value for name, value in query.operations if name == "filter")
        assert first_filter[0].right.value == "agent_a"


def test_streaming_chat_schedules_memory_with_current_conversation_id():
    class StreamingChatHandler:
        def __init__(self):
            self._last_user_conv_id = None

        def chat_stream(self, user_message, intent=None, agent_id=None):
            self._last_user_conv_id = 42
            yield "Hello"
            yield " there"

    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = "agent_a"
    brain.decision_engine = MagicMock()
    brain.decision_engine.decide.return_value = Action.CHAT
    brain.chat_handler = StreamingChatHandler()
    brain.memory_extractor = MagicMock()
    brain._executor = MagicMock()

    assert list(brain.process_stream("hello")) == ["Hello", " there"]
    brain._executor.submit.assert_called_once_with(
        brain.memory_extractor.extract_memory,
        "hello",
        source_conversation_id=42,
        agent_id="agent_a",
    )


def test_oversized_stream_clears_previous_conversation_id():
    handler = ChatHandler(
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    )
    handler._last_user_conv_id = 99

    with patch("handlers.chat_handler.settings.max_input_length", 3):
        result = list(handler.chat_stream("too long"))

    assert result
    assert handler._last_user_conv_id is None


def test_non_chat_process_uses_created_user_conversation_id():
    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = "agent_a"
    brain.current_session = SimpleNamespace(id="session_a")
    brain.decision_engine = MagicMock()
    brain.decision_engine.decide.return_value = Action.USE_TOOL
    brain.embedding_service = MagicMock()
    brain.embedding_service.generate_embedding.return_value = [0.1] * 768
    brain.conversation_repo = MagicMock()
    brain.conversation_repo.create.side_effect = [
        SimpleNamespace(id=73),
        SimpleNamespace(id=74),
    ]
    brain.agent_loop = MagicMock()
    brain.agent_loop.run.return_value = "done"
    brain.session_repo = MagicMock()
    brain.memory_extractor = MagicMock()
    brain._executor = MagicMock()

    assert brain.process("calculate something") == "done"
    brain.conversation_repo.trim.assert_called_once_with(agent_id="agent_a")
    brain._executor.submit.assert_called_once_with(
        brain.memory_extractor.extract_memory,
        "calculate something",
        source_conversation_id=73,
        agent_id="agent_a",
    )


def test_memory_retrieval_skips_repository_when_embedding_is_unavailable():
    memory_repo = MagicMock()
    embedding_service = MagicMock()
    embedding_service.generate_embedding.return_value = None
    service = MemoryRetrievalService(memory_repo, embedding_service)

    assert service.retrieve("remember this", agent_id="agent_a") == []
    memory_repo.semantic_search.assert_not_called()


def test_explicit_memory_store_reports_embedding_failure_without_writing():
    memory_repo = MagicMock()
    embedding_service = MagicMock()
    embedding_service.generate_embedding.return_value = None
    handler = MemoryHandler(memory_repo, embedding_service)

    result = handler.store_memory(
        "remember project: a meaningful project",
        agent_id="agent_a",
    )

    assert "embeddings are unavailable" in result
    memory_repo.create.assert_not_called()


def test_context_fallback_skips_vector_queries_without_embedding():
    memory_repo = MagicMock()
    conversation_repo = MagicMock()
    conversation_repo.get_by_session.return_value = []
    embedding_service = MagicMock()
    embedding_service.generate_embedding.return_value = None
    session_repo = MagicMock()
    session_repo.get_recent_with_summaries.return_value = []
    context_manager = ContextManager(
        memory_repo,
        conversation_repo,
        embedding_service,
        retrieval_service=None,
        session_repo=session_repo,
    )

    result = context_manager.build_context(
        "hello",
        session_id="session_a",
        agent_id="agent_a",
    )

    assert result["memory_context"] == ""
    assert result["cross_session_context"] == ""
    memory_repo.semantic_search.assert_not_called()
    conversation_repo.search_across_sessions.assert_not_called()
