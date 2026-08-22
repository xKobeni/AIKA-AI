from contextlib import contextmanager
from unittest.mock import MagicMock, Mock, patch

import pytest


def test_session_delete_removes_conversations_then_session_in_one_context():
    from database.models import Conversation, Memory, Session
    from repositories.session_repository import SessionRepository

    db = MagicMock()
    conversation_query = MagicMock()
    conversation_query.filter.return_value.delete.return_value = 4
    conversation_id_query = MagicMock()
    conversation_id_query.filter.return_value = conversation_id_query
    memory_query = MagicMock()
    memory_query.filter.return_value.update.return_value = 2
    session_query = MagicMock()
    session_query.filter.return_value.delete.return_value = 1

    def query_for(model):
        if model is Conversation.id:
            return conversation_id_query
        if model is Conversation:
            return conversation_query
        if model is Memory:
            return memory_query
        if model is Session:
            return session_query
        raise AssertionError(f"Unexpected model: {model}")

    db.query.side_effect = query_for

    @contextmanager
    def fake_session():
        yield db

    with patch("repositories.session_repository.db_session", fake_session):
        result = SessionRepository().delete("session-1")

    assert result == {
        "session_deleted": True,
        "conversations_deleted": 4,
        "memories_unlinked": 2,
    }
    memory_query.filter.return_value.update.assert_called_once_with(
        {Memory.source_conversation_id: None},
        synchronize_session=False,
    )
    conversation_query.filter.return_value.delete.assert_called_once_with(
        synchronize_session=False
    )
    session_query.filter.return_value.delete.assert_called_once_with(
        synchronize_session=False
    )
    assert db.query.call_args_list == [
        ((Conversation.id,),),
        ((Memory,),),
        ((Conversation,),),
        ((Session,),),
    ]


def test_session_delete_reports_missing_session_without_touching_other_scope():
    from repositories.session_repository import SessionRepository

    db = MagicMock()
    db.query.return_value.filter.return_value.update.return_value = 0
    db.query.return_value.filter.return_value.delete.side_effect = [0, 0]

    @contextmanager
    def fake_session():
        yield db

    with patch("repositories.session_repository.db_session", fake_session):
        result = SessionRepository().delete("missing")

    assert result == {
        "session_deleted": False,
        "conversations_deleted": 0,
        "memories_unlinked": 0,
    }


def test_orm_declares_session_cascade_and_memory_source_policy():
    from database.models import Conversation, Memory

    session_fk = next(iter(Conversation.__table__.c.session_id.foreign_keys))
    source_fk = next(iter(Memory.__table__.c.source_conversation_id.foreign_keys))

    assert session_fk.target_fullname == "sessions.id"
    assert session_fk.ondelete == "CASCADE"
    assert source_fk.target_fullname == "conversations.id"
    assert source_fk.ondelete == "SET NULL"


def test_json_registry_is_the_only_active_agent_persistence_model(tmp_path):
    from agents.agent_registry import AgentRegistry
    from database.base import Base

    assert "agents" not in Base.metadata.tables
    registry = AgentRegistry(data_path=str(tmp_path / "agents.json"))
    assert registry.create_agent("phase4", "Phase 4 Agent") is not None
    assert registry.get("phase4").name == "Phase 4 Agent"


def test_embedding_schema_validation_accepts_expected_dimensions():
    from database.migrations import validate_embedding_schema

    connection = MagicMock()
    connection.dialect.name = "postgresql"
    connection.execute.return_value.all.return_value = [
        ("memories", "embedding", "vector(768)"),
        ("conversations", "embedding", "vector(768)"),
    ]

    validate_embedding_schema(connection)


def test_embedding_schema_validation_blocks_dimension_mismatch():
    from database.migrations import MigrationBlockedError, validate_embedding_schema

    connection = MagicMock()
    connection.dialect.name = "postgresql"
    connection.execute.return_value.all.return_value = [
        ("memories", "embedding", "vector(384)"),
        ("conversations", "embedding", "vector(768)"),
    ]

    with pytest.raises(MigrationBlockedError, match="memories.embedding"):
        validate_embedding_schema(connection)


def test_foreign_key_migration_blocks_orphan_conversations_before_ddl():
    from database.migrations import (
        MigrationBlockedError,
        _migration_001_conversation_foreign_keys,
    )

    connection = MagicMock()
    connection.execute.return_value.scalar.return_value = 3

    with pytest.raises(MigrationBlockedError, match="3 orphan conversations"):
        _migration_001_conversation_foreign_keys(connection)

    assert connection.execute.call_count == 1


def test_migration_dry_run_lists_pending_without_beginning_transaction():
    from database.migrations import MIGRATIONS, MigrationRunner

    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    inspector = MagicMock()
    inspector.has_table.return_value = False

    with patch("database.migrations.inspect", return_value=inspector):
        pending = MigrationRunner(engine).migrate(dry_run=True)

    assert pending == list(MIGRATIONS)
    engine.begin.assert_not_called()


def test_migration_status_excludes_already_applied_versions():
    from database.migrations import MIGRATIONS, MigrationRunner

    engine = MagicMock()
    connection = MagicMock()
    engine.connect.return_value.__enter__.return_value = connection
    connection.execute.return_value.scalar.return_value = 1
    inspector = MagicMock()
    inspector.has_table.return_value = True

    with patch("database.migrations.inspect", return_value=inspector):
        status = MigrationRunner(engine).status()

    assert status["current_version"] == 1
    assert status["latest_version"] == 2
    assert status["pending"] == [MIGRATIONS[1]]


def test_each_migration_uses_its_own_transaction_and_records_version():
    from database.migrations import Migration, MigrationRunner

    first_apply = Mock()
    second_apply = Mock()
    migrations = (
        Migration(1, "first", first_apply),
        Migration(2, "second", second_apply),
    )
    engine = MagicMock()
    connection = MagicMock()
    engine.begin.return_value.__enter__.return_value = connection
    runner = MigrationRunner(engine)

    with patch.object(
        runner,
        "status",
        return_value={"current_version": 0, "latest_version": 2,
                      "pending": list(migrations)},
    ), patch("database.migrations.MIGRATIONS", migrations), patch(
        "database.migrations.validate_embedding_schema"
    ) as validate:
        applied = runner.migrate()

    assert applied == list(migrations)
    assert engine.begin.call_count == 3  # version table + one per migration
    first_apply.assert_called_once_with(connection)
    second_apply.assert_called_once_with(connection)
    assert validate.call_count == 2


def test_up_to_date_migration_run_is_a_noop():
    from database.migrations import MigrationRunner

    engine = MagicMock()
    runner = MigrationRunner(engine)
    with patch.object(
        runner,
        "status",
        return_value={"current_version": 2, "latest_version": 2, "pending": []},
    ):
        assert runner.migrate() == []

    engine.begin.assert_not_called()
