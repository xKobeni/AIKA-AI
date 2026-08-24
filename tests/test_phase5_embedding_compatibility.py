from unittest.mock import MagicMock, Mock, patch

import pytest


def test_declared_dimension_accepts_768_values():
    from database.embedding_compatibility import validate_embedding_vector

    embedding = [0.1] * 768
    assert validate_embedding_vector(embedding) is embedding


@pytest.mark.parametrize("dimension", [384, 1024])
def test_generated_embedding_dimension_mismatch_returns_safe_fallback(dimension):
    from database.embedding_compatibility import EmbeddingDimensionError
    from llm.embedding_service import EmbeddingService

    with patch(
        "llm.embedding_service.ollama.embed",
        return_value={"embeddings": [[0.1] * dimension]},
    ):
        service = EmbeddingService()
        result = service.generate_embedding("dimension check")

    assert result is None
    assert isinstance(service.last_error, EmbeddingDimensionError)
    assert service.last_error.expected == 768
    assert service.last_error.actual == dimension


@pytest.mark.parametrize("dimension", [384, 1024])
def test_conversation_vectors_are_rejected_before_repository_access(dimension):
    from database.embedding_compatibility import EmbeddingDimensionError
    from repositories.conversation_repository import ConversationRepository

    repository = ConversationRepository()
    invalid = [0.1] * dimension

    with patch("repositories.conversation_repository.db_session") as db_session:
        with pytest.raises(EmbeddingDimensionError):
            repository.create("user", "hello", embedding=invalid)
        with pytest.raises(EmbeddingDimensionError):
            repository.semantic_search(invalid)
        with pytest.raises(EmbeddingDimensionError):
            repository.search_across_sessions(invalid, "current")

    db_session.assert_not_called()


@pytest.mark.parametrize("dimension", [384, 1024])
def test_memory_vectors_are_rejected_before_repository_access(dimension):
    from database.embedding_compatibility import EmbeddingDimensionError
    from repositories.memory_repository import MemoryRepository

    repository = MemoryRepository()
    invalid = [0.1] * dimension

    with patch("repositories.memory_repository.db_session") as db_session:
        with pytest.raises(EmbeddingDimensionError):
            repository.create("fact", "content", invalid)
        with pytest.raises(EmbeddingDimensionError):
            repository.semantic_search(invalid)

    db_session.assert_not_called()


def test_startup_rejects_dimension_that_does_not_match_schema():
    from database.embedding_compatibility import EmbeddingConfigurationError
    from llm.embedding_service import EmbeddingService

    with patch("llm.embedding_service.settings") as mock_settings, patch(
        "llm.embedding_service.ollama.Client"
    ) as client_class:
        mock_settings.embedding_model = "different-size-model"
        mock_settings.embedding_dimension = 384
        mock_settings.ollama_host = "http://localhost:11434"
        mock_settings.llm_timeout = 30

        with pytest.raises(EmbeddingConfigurationError, match="database migration"):
            EmbeddingService()

    client_class.assert_not_called()


def test_migration_validation_blocks_config_mismatch_before_schema_query():
    from database.migrations import MigrationBlockedError, validate_embedding_schema

    connection = MagicMock()
    connection.dialect.name = "postgresql"

    with pytest.raises(MigrationBlockedError, match="database migration"):
        validate_embedding_schema(connection, expected_dimension=1024)

    connection.execute.assert_not_called()


def test_embedding_refresh_preserves_startup_contract_and_refreshes_connection():
    from llm.embedding_service import EmbeddingService

    with patch("llm.embedding_service.settings") as mock_settings, patch(
        "llm.embedding_service.ollama.Client"
    ) as client_class:
        mock_settings.embedding_model = "startup-model"
        mock_settings.embedding_dimension = 768
        mock_settings.ollama_host = "http://first:11434"
        mock_settings.llm_timeout = 20
        service = EmbeddingService()

        mock_settings.embedding_model = "runtime-model"
        mock_settings.embedding_dimension = 1024
        mock_settings.ollama_host = "http://second:11434"
        mock_settings.llm_timeout = 45
        service.refresh_from_settings()

    assert service.model == "startup-model"
    assert service.dimension == 768
    assert service.host == "http://second:11434"
    assert service.timeout == 45
    assert client_class.call_args_list[-1].kwargs == {
        "host": "http://second:11434",
        "timeout": 45,
    }


@pytest.mark.parametrize(
    ("key", "value"),
    [("embedding_model", "replacement-model"), ("embedding_dimension", "1024")],
)
def test_runtime_embedding_changes_require_restart_and_schema_check(key, value):
    from config.settings import settings
    from handlers.config_handler import ConfigHandler

    refresh = Mock()
    original = getattr(settings, key)
    try:
        message = ConfigHandler(refresh_callback=refresh)._set_value(
            f"{key}={value}"
        )
    finally:
        setattr(settings, key, original)

    refresh.assert_not_called()
    assert "restart AIKA" in message
    assert "schema compatibility" in message
    assert "database migration" in message
