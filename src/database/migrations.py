from dataclasses import dataclass
from datetime import datetime, timezone

from sqlalchemy import inspect, text

from database.models import EMBEDDING_DIMENSION


class MigrationBlockedError(RuntimeError):
    pass


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    apply: object


def validate_embedding_schema(connection):
    if connection.dialect.name != "postgresql":
        raise MigrationBlockedError(
            "AIKA schema validation requires PostgreSQL with pgvector."
        )

    rows = connection.execute(text("""
        SELECT c.relname, a.attname, format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = current_schema()
          AND c.relname IN ('memories', 'conversations')
          AND a.attname = 'embedding'
          AND a.attnum > 0
          AND NOT a.attisdropped
    """)).all()
    actual = {(table, column): type_name for table, column, type_name in rows}
    expected_type = f"vector({EMBEDDING_DIMENSION})"
    for table in ("memories", "conversations"):
        found = actual.get((table, "embedding"))
        if found != expected_type:
            raise MigrationBlockedError(
                f"{table}.embedding must be {expected_type}; found {found!r}."
            )


def _constraint_exists(connection, name):
    return bool(connection.execute(text("""
        SELECT 1 FROM pg_constraint WHERE conname = :name
    """), {"name": name}).scalar())


def _migration_001_conversation_foreign_keys(connection):
    orphan_sessions = connection.execute(text("""
        SELECT count(*)
        FROM conversations c
        LEFT JOIN sessions s ON s.id = c.session_id
        WHERE c.session_id IS NOT NULL AND s.id IS NULL
    """)).scalar()
    if orphan_sessions:
        raise MigrationBlockedError(
            f"Cannot add session cascade: {orphan_sessions} orphan conversations exist."
        )

    orphan_sources = connection.execute(text("""
        SELECT count(*)
        FROM memories m
        LEFT JOIN conversations c ON c.id = m.source_conversation_id
        WHERE m.source_conversation_id IS NOT NULL AND c.id IS NULL
    """)).scalar()
    if orphan_sources:
        raise MigrationBlockedError(
            f"Cannot add memory source key: {orphan_sources} orphan references exist."
        )

    if not _constraint_exists(connection, "fk_conversations_session"):
        connection.execute(text("""
            ALTER TABLE conversations
            ADD CONSTRAINT fk_conversations_session
            FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
        """))
    if not _constraint_exists(connection, "fk_memories_source_conversation"):
        connection.execute(text("""
            ALTER TABLE memories
            ADD CONSTRAINT fk_memories_source_conversation
            FOREIGN KEY (source_conversation_id)
            REFERENCES conversations(id) ON DELETE SET NULL
        """))


def _migration_002_retire_legacy_agent_table(connection):
    inspector = inspect(connection)
    has_agents = inspector.has_table("agents")
    has_legacy = inspector.has_table("agents_legacy")
    if not has_agents:
        return
    if has_legacy:
        raise MigrationBlockedError(
            "Both agents and agents_legacy exist; resolve them manually."
        )
    connection.execute(text("ALTER TABLE agents RENAME TO agents_legacy"))


MIGRATIONS = (
    Migration(1, "conversation lifecycle foreign keys", _migration_001_conversation_foreign_keys),
    Migration(2, "retire unused ORM agent table", _migration_002_retire_legacy_agent_table),
)


class MigrationRunner:
    def __init__(self, engine):
        self.engine = engine

    def _current_version(self, connection):
        if not inspect(connection).has_table("schema_version"):
            return 0
        value = connection.execute(
            text("SELECT max(version) FROM schema_version")
        ).scalar()
        return int(value or 0)

    def status(self):
        with self.engine.connect() as connection:
            current = self._current_version(connection)
        return {
            "current_version": current,
            "latest_version": MIGRATIONS[-1].version if MIGRATIONS else 0,
            "pending": [m for m in MIGRATIONS if m.version > current],
        }

    def migrate(self, dry_run=False):
        status = self.status()
        pending = status["pending"]
        if dry_run:
            return pending
        if not pending:
            return []

        with self.engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE IF NOT EXISTS schema_version (
                    version INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    applied_at TIMESTAMPTZ NOT NULL
                )
            """))

        applied = []
        for migration in pending:
            with self.engine.begin() as connection:
                validate_embedding_schema(connection)
                migration.apply(connection)
                connection.execute(text("""
                    INSERT INTO schema_version (version, name, applied_at)
                    VALUES (:version, :name, :applied_at)
                """), {
                    "version": migration.version,
                    "name": migration.name,
                    "applied_at": datetime.now(timezone.utc),
                })
            applied.append(migration)
        return applied
