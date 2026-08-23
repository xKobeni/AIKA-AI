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


def _migration_003_durable_jobs(connection):
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS jobs (
            id VARCHAR(32) PRIMARY KEY,
            job_type VARCHAR(100) NOT NULL,
            payload JSONB NOT NULL,
            status VARCHAR(30) NOT NULL,
            owner_id VARCHAR(100),
            agent_id VARCHAR(50),
            session_id VARCHAR(50),
            idempotency_key VARCHAR(200),
            progress INTEGER NOT NULL DEFAULT 0,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 3,
            result JSONB,
            error_type VARCHAR(200),
            cancel_requested BOOLEAN NOT NULL DEFAULT FALSE,
            approval_request JSONB,
            approval_granted BOOLEAN,
            available_at TIMESTAMPTZ NOT NULL,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            CONSTRAINT uq_jobs_idempotency_key UNIQUE (idempotency_key),
            CONSTRAINT ck_jobs_status CHECK (
                status IN (
                    'queued', 'running', 'waiting_approval',
                    'succeeded', 'failed', 'cancelled'
                )
            ),
            CONSTRAINT ck_jobs_progress CHECK (progress BETWEEN 0 AND 100),
            CONSTRAINT ck_jobs_max_attempts CHECK (max_attempts > 0),
            CONSTRAINT ck_jobs_attempt_count CHECK (attempt_count >= 0)
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS job_events (
            id BIGSERIAL PRIMARY KEY,
            job_id VARCHAR(32) NOT NULL
                REFERENCES jobs(id) ON DELETE CASCADE,
            event_type VARCHAR(50) NOT NULL,
            data JSONB NOT NULL,
            created_at TIMESTAMPTZ NOT NULL
        )
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_jobs_claim
        ON jobs (status, available_at, created_at)
    """))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_jobs_job_type ON jobs (job_type)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_jobs_owner_id ON jobs (owner_id)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_jobs_agent_id ON jobs (agent_id)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_jobs_session_id ON jobs (session_id)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_job_events_job_id ON job_events (job_id)"
    ))

    inspector = inspect(connection)
    required_columns = {
        "jobs": {
            "id", "job_type", "payload", "status", "owner_id", "agent_id",
            "session_id", "idempotency_key", "progress", "attempt_count",
            "max_attempts", "result", "error_type", "cancel_requested",
            "approval_request", "approval_granted", "available_at", "created_at",
            "updated_at", "started_at", "finished_at",
        },
        "job_events": {"id", "job_id", "event_type", "data", "created_at"},
    }
    for table_name, expected in required_columns.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(expected - actual)
        if missing:
            raise MigrationBlockedError(
                f"{table_name} is missing required columns: {', '.join(missing)}"
            )

    unique_columns = {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints("jobs")
    }
    if ("idempotency_key",) not in unique_columns:
        raise MigrationBlockedError(
            "jobs.idempotency_key must have a unique constraint."
        )

    event_foreign_keys = inspector.get_foreign_keys("job_events")
    has_job_event_key = any(
        item.get("constrained_columns") == ["job_id"]
        and item.get("referred_table") == "jobs"
        and (item.get("options") or {}).get("ondelete") == "CASCADE"
        for item in event_foreign_keys
    )
    if not has_job_event_key:
        raise MigrationBlockedError(
            "job_events.job_id must cascade deletes from jobs.id."
        )


def _migration_004_durable_reminders(connection):
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS reminders (
            id VARCHAR(32) PRIMARY KEY,
            message TEXT NOT NULL,
            timezone VARCHAR(64) NOT NULL,
            recurrence JSONB,
            status VARCHAR(20) NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1,
            trigger_count INTEGER NOT NULL DEFAULT 0,
            next_run_at TIMESTAMPTZ,
            next_job_id VARCHAR(32) REFERENCES jobs(id) ON DELETE SET NULL,
            owner_id VARCHAR(100),
            agent_id VARCHAR(50),
            session_id VARCHAR(50),
            idempotency_key VARCHAR(200),
            last_triggered_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            cancelled_at TIMESTAMPTZ,
            CONSTRAINT uq_reminders_idempotency_key UNIQUE (idempotency_key),
            CONSTRAINT ck_reminders_status CHECK (
                status IN ('active', 'completed', 'cancelled')
            ),
            CONSTRAINT ck_reminders_revision CHECK (revision > 0),
            CONSTRAINT ck_reminders_trigger_count CHECK (trigger_count >= 0)
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS reminder_occurrences (
            id VARCHAR(32) PRIMARY KEY,
            reminder_id VARCHAR(32) NOT NULL
                REFERENCES reminders(id) ON DELETE CASCADE,
            revision INTEGER NOT NULL,
            job_id VARCHAR(32) REFERENCES jobs(id) ON DELETE SET NULL,
            scheduled_for TIMESTAMPTZ NOT NULL,
            triggered_at TIMESTAMPTZ NOT NULL,
            acknowledged_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL,
            CONSTRAINT uq_reminder_occurrence_schedule UNIQUE (
                reminder_id, revision, scheduled_for
            ),
            CONSTRAINT ck_reminder_occurrences_revision CHECK (revision > 0)
        )
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_reminders_due
        ON reminders (status, next_run_at)
    """))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_reminders_owner_id "
        "ON reminders (owner_id)"
    ))
    connection.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_reminders_agent_id "
        "ON reminders (agent_id)"
    ))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_reminder_occurrences_due
        ON reminder_occurrences (acknowledged_at, scheduled_for)
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_reminder_occurrences_reminder_id
        ON reminder_occurrences (reminder_id)
    """))

    inspector = inspect(connection)
    required_columns = {
        "reminders": {
            "id", "message", "timezone", "recurrence", "status",
            "revision", "trigger_count", "next_run_at", "next_job_id",
            "owner_id", "agent_id", "session_id", "idempotency_key",
            "last_triggered_at", "created_at", "updated_at", "cancelled_at",
        },
        "reminder_occurrences": {
            "id", "reminder_id", "revision", "job_id", "scheduled_for",
            "triggered_at", "acknowledged_at", "created_at",
        },
    }
    for table_name, expected in required_columns.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(expected - actual)
        if missing:
            raise MigrationBlockedError(
                f"{table_name} is missing required columns: {', '.join(missing)}"
            )

    unique_columns = {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints("reminders")
    }
    if ("idempotency_key",) not in unique_columns:
        raise MigrationBlockedError(
            "reminders.idempotency_key must have a unique constraint."
        )

    occurrence_unique_columns = {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints("reminder_occurrences")
    }
    if ("reminder_id", "revision", "scheduled_for") not in occurrence_unique_columns:
        raise MigrationBlockedError(
            "reminder occurrences must be unique per revision and schedule."
        )

    reminder_foreign_keys = inspector.get_foreign_keys("reminders")
    has_next_job_key = any(
        item.get("constrained_columns") == ["next_job_id"]
        and item.get("referred_table") == "jobs"
        and (item.get("options") or {}).get("ondelete") == "SET NULL"
        for item in reminder_foreign_keys
    )
    if not has_next_job_key:
        raise MigrationBlockedError(
            "reminders.next_job_id must reference jobs.id with SET NULL."
        )

    occurrence_foreign_keys = inspector.get_foreign_keys(
        "reminder_occurrences"
    )
    required_occurrence_keys = {
        ("reminder_id", "reminders", "CASCADE"),
        ("job_id", "jobs", "SET NULL"),
    }
    actual_occurrence_keys = {
        (
            (item.get("constrained_columns") or [None])[0],
            item.get("referred_table"),
            (item.get("options") or {}).get("ondelete"),
        )
        for item in occurrence_foreign_keys
    }
    if not required_occurrence_keys.issubset(actual_occurrence_keys):
        raise MigrationBlockedError(
            "reminder occurrence foreign-key policies are invalid."
        )


def _migration_005_persistent_orchestration(connection):
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS orchestration_runs (
            id VARCHAR(32) PRIMARY KEY,
            kind VARCHAR(20) NOT NULL,
            task TEXT NOT NULL,
            agent_ids JSONB NOT NULL,
            status VARCHAR(30) NOT NULL,
            revision INTEGER NOT NULL DEFAULT 1,
            allow_high_tools BOOLEAN NOT NULL DEFAULT FALSE,
            current_job_id VARCHAR(32) REFERENCES jobs(id) ON DELETE SET NULL,
            owner_id VARCHAR(100),
            agent_id VARCHAR(50),
            session_id VARCHAR(50),
            idempotency_key VARCHAR(200),
            result JSONB,
            error_type VARCHAR(200),
            total_steps INTEGER NOT NULL,
            completed_steps INTEGER NOT NULL DEFAULT 0,
            max_turns INTEGER NOT NULL DEFAULT 1,
            approved_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            cancelled_at TIMESTAMPTZ,
            CONSTRAINT uq_orchestration_runs_idempotency_key
                UNIQUE (idempotency_key),
            CONSTRAINT ck_orchestration_runs_kind CHECK (
                kind IN ('delegate', 'chain', 'parallel', 'team')
            ),
            CONSTRAINT ck_orchestration_runs_status CHECK (
                status IN (
                    'queued', 'running', 'waiting_approval',
                    'completed', 'failed', 'cancelled'
                )
            ),
            CONSTRAINT ck_orchestration_runs_revision CHECK (revision > 0),
            CONSTRAINT ck_orchestration_runs_total_steps CHECK (total_steps > 0),
            CONSTRAINT ck_orchestration_runs_completed_steps CHECK (
                completed_steps >= 0 AND completed_steps <= total_steps
            ),
            CONSTRAINT ck_orchestration_runs_max_turns CHECK (max_turns > 0)
        )
    """))
    connection.execute(text("""
        CREATE TABLE IF NOT EXISTS orchestration_steps (
            id VARCHAR(32) PRIMARY KEY,
            run_id VARCHAR(32) NOT NULL
                REFERENCES orchestration_runs(id) ON DELETE CASCADE,
            position INTEGER NOT NULL,
            agent_id VARCHAR(50) NOT NULL,
            turn INTEGER,
            depends_on_step_id VARCHAR(32)
                REFERENCES orchestration_steps(id) ON DELETE SET NULL,
            status VARCHAR(20) NOT NULL,
            input_text TEXT,
            result_text TEXT,
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 2,
            error_type VARCHAR(200),
            created_at TIMESTAMPTZ NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL,
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ,
            CONSTRAINT uq_orchestration_steps_position UNIQUE (run_id, position),
            CONSTRAINT ck_orchestration_steps_status CHECK (
                status IN (
                    'pending', 'running', 'completed',
                    'failed', 'cancelled', 'skipped'
                )
            ),
            CONSTRAINT ck_orchestration_steps_position CHECK (position >= 0),
            CONSTRAINT ck_orchestration_steps_attempt_count
                CHECK (attempt_count >= 0),
            CONSTRAINT ck_orchestration_steps_max_attempts
                CHECK (max_attempts > 0)
        )
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_orchestration_runs_status
        ON orchestration_runs (status, created_at)
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_orchestration_runs_owner_id
        ON orchestration_runs (owner_id)
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_orchestration_runs_agent_id
        ON orchestration_runs (agent_id)
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_orchestration_runs_session_id
        ON orchestration_runs (session_id)
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_orchestration_steps_run_status
        ON orchestration_steps (run_id, status)
    """))
    connection.execute(text("""
        CREATE INDEX IF NOT EXISTS ix_orchestration_steps_agent_id
        ON orchestration_steps (agent_id)
    """))

    inspector = inspect(connection)
    required_columns = {
        "orchestration_runs": {
            "id", "kind", "task", "agent_ids", "status", "revision",
            "allow_high_tools", "current_job_id", "owner_id", "agent_id",
            "session_id", "idempotency_key", "result", "error_type",
            "total_steps", "completed_steps", "max_turns", "approved_at",
            "created_at", "updated_at", "started_at", "finished_at",
            "cancelled_at",
        },
        "orchestration_steps": {
            "id", "run_id", "position", "agent_id", "turn",
            "depends_on_step_id", "status", "input_text", "result_text",
            "attempt_count", "max_attempts", "error_type", "created_at",
            "updated_at", "started_at", "finished_at",
        },
    }
    for table_name, expected in required_columns.items():
        actual = {column["name"] for column in inspector.get_columns(table_name)}
        missing = sorted(expected - actual)
        if missing:
            raise MigrationBlockedError(
                f"{table_name} is missing required columns: {', '.join(missing)}"
            )

    run_unique_columns = {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints("orchestration_runs")
    }
    if ("idempotency_key",) not in run_unique_columns:
        raise MigrationBlockedError(
            "orchestration_runs.idempotency_key must be unique."
        )
    step_unique_columns = {
        tuple(item.get("column_names") or ())
        for item in inspector.get_unique_constraints("orchestration_steps")
    }
    if ("run_id", "position") not in step_unique_columns:
        raise MigrationBlockedError(
            "orchestration steps must be unique by run and position."
        )

    run_foreign_keys = inspector.get_foreign_keys("orchestration_runs")
    has_current_job_key = any(
        item.get("constrained_columns") == ["current_job_id"]
        and item.get("referred_table") == "jobs"
        and (item.get("options") or {}).get("ondelete") == "SET NULL"
        for item in run_foreign_keys
    )
    if not has_current_job_key:
        raise MigrationBlockedError(
            "orchestration_runs.current_job_id must reference jobs.id with SET NULL."
        )

    step_foreign_keys = inspector.get_foreign_keys("orchestration_steps")
    required_step_keys = {
        ("run_id", "orchestration_runs", "CASCADE"),
        ("depends_on_step_id", "orchestration_steps", "SET NULL"),
    }
    actual_step_keys = {
        (
            (item.get("constrained_columns") or [None])[0],
            item.get("referred_table"),
            (item.get("options") or {}).get("ondelete"),
        )
        for item in step_foreign_keys
    }
    if not required_step_keys.issubset(actual_step_keys):
        raise MigrationBlockedError(
            "orchestration step foreign-key policies are invalid."
        )


MIGRATIONS = (
    Migration(1, "conversation lifecycle foreign keys", _migration_001_conversation_foreign_keys),
    Migration(2, "retire unused ORM agent table", _migration_002_retire_legacy_agent_table),
    Migration(3, "durable background jobs", _migration_003_durable_jobs),
    Migration(4, "durable reminders and occurrences", _migration_004_durable_reminders),
    Migration(5, "persistent orchestration runs and steps", _migration_005_persistent_orchestration),
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
