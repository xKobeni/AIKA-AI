from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Index,
    Integer,
    String,
    Text,
    DateTime,
    ForeignKey,
    UniqueConstraint,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from datetime import datetime, timezone

from database.base import Base

from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects.postgresql import JSONB

EMBEDDING_DIMENSION = 768

class Memory(Base):

    __tablename__ = "memories"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    type: Mapped[str] = mapped_column(
        String(50)
    )

    content: Mapped[str] = mapped_column(
        Text
    )

    embedding: Mapped[list] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=True
    )
    
    importance: Mapped[int] = mapped_column(
        Integer,
        default=5
    )

    access_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )
    
    category: Mapped[str] = mapped_column(
        String(50), default="fact"
    )

    last_accessed: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    profile_score: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    source_conversation_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("conversations.id", ondelete="SET NULL"),
        nullable=True
    )

    agent_id: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True
    )

    __table_args__ = (
        Index(
            "ix_memories_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_cosine_ops"},
            postgresql_where=embedding.isnot(None),
        ),
    )
    
# -----------------------------------------------------------------------------


class Conversation(Base):

    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(
        Integer,
        primary_key=True
    )

    session_id: Mapped[str] = mapped_column(
        String(50),
        ForeignKey("sessions.id", ondelete="CASCADE"),
        index=True,
        nullable=True
    )

    role: Mapped[str] = mapped_column(
        String(20)
    )

    content: Mapped[str] = mapped_column(
        Text
    )

    tool_used: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )

    embedding: Mapped[list] = mapped_column(
        Vector(EMBEDDING_DIMENSION),
        nullable=True
    )

    intent: Mapped[str] = mapped_column(
        String(50),
        nullable=True
    )

    model_used: Mapped[str] = mapped_column(
        String(100),
        nullable=True
    )

    response_time_ms: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    token_count: Mapped[int] = mapped_column(
        Integer,
        nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    agent_id: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True
    )

    __table_args__ = (
        Index(
            "ix_conversations_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_ops={"embedding": "vector_l2_ops"},
            postgresql_where=embedding.isnot(None),
        ),
    )

# -----------------------------------------------------------------------------


class Session(Base):

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(
        String(50),
        primary_key=True
    )

    started_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    last_active: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc)
    )

    message_count: Mapped[int] = mapped_column(
        Integer,
        default=0
    )

    summary: Mapped[str] = mapped_column(
        Text,
        nullable=True
    )

    agent_id: Mapped[str] = mapped_column(
        String(50),
        nullable=True,
        index=True
    )


# -----------------------------------------------------------------------------


class Job(Base):

    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
        CheckConstraint(
            "status IN ('queued', 'running', 'waiting_approval', "
            "'succeeded', 'failed', 'cancelled')",
            name="ck_jobs_status",
        ),
        CheckConstraint(
            "progress BETWEEN 0 AND 100", name="ck_jobs_progress"
        ),
        CheckConstraint("max_attempts > 0", name="ck_jobs_max_attempts"),
        CheckConstraint("attempt_count >= 0", name="ck_jobs_attempt_count"),
        Index("ix_jobs_claim", "status", "available_at", "created_at"),
        Index("ix_jobs_job_type", "job_type"),
        Index("ix_jobs_owner_id", "owner_id"),
        Index("ix_jobs_agent_id", "agent_id"),
        Index("ix_jobs_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(100))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30))
    owner_id: Mapped[str] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=True)
    progress: Mapped[int] = mapped_column(Integer, default=0)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    result: Mapped[object] = mapped_column(JSONB, nullable=True)
    error_type: Mapped[str] = mapped_column(String(200), nullable=True)
    cancel_requested: Mapped[bool] = mapped_column(Boolean, default=False)
    approval_request: Mapped[dict] = mapped_column(JSONB, nullable=True)
    approval_granted: Mapped[bool] = mapped_column(Boolean, nullable=True)
    available_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class JobEvent(Base):

    __tablename__ = "job_events"
    __table_args__ = (Index("ix_job_events_job_id", "job_id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    job_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    event_type: Mapped[str] = mapped_column(String(50), nullable=False)
    data: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# -----------------------------------------------------------------------------


class Reminder(Base):

    __tablename__ = "reminders"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_reminders_idempotency_key"
        ),
        CheckConstraint(
            "status IN ('active', 'completed', 'cancelled')",
            name="ck_reminders_status",
        ),
        CheckConstraint("revision > 0", name="ck_reminders_revision"),
        CheckConstraint(
            "trigger_count >= 0", name="ck_reminders_trigger_count"
        ),
        Index("ix_reminders_due", "status", "next_run_at"),
        Index("ix_reminders_owner_id", "owner_id"),
        Index("ix_reminders_agent_id", "agent_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False)
    recurrence: Mapped[dict] = mapped_column(JSONB, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    trigger_count: Mapped[int] = mapped_column(Integer, default=0)
    next_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    next_job_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[str] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=True)
    last_triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class ReminderOccurrence(Base):

    __tablename__ = "reminder_occurrences"
    __table_args__ = (
        UniqueConstraint(
            "reminder_id", "revision", "scheduled_for",
            name="uq_reminder_occurrence_schedule",
        ),
        CheckConstraint(
            "revision > 0", name="ck_reminder_occurrences_revision"
        ),
        Index(
            "ix_reminder_occurrences_due",
            "acknowledged_at",
            "scheduled_for",
        ),
        Index("ix_reminder_occurrences_reminder_id", "reminder_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    reminder_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("reminders.id", ondelete="CASCADE"),
        nullable=False,
    )
    revision: Mapped[int] = mapped_column(Integer, nullable=False)
    job_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    scheduled_for: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    triggered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    acknowledged_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


# -----------------------------------------------------------------------------


class OrchestrationRun(Base):

    __tablename__ = "orchestration_runs"
    __table_args__ = (
        UniqueConstraint(
            "idempotency_key", name="uq_orchestration_runs_idempotency_key"
        ),
        CheckConstraint(
            "kind IN ('delegate', 'chain', 'parallel', 'team')",
            name="ck_orchestration_runs_kind",
        ),
        CheckConstraint(
            "status IN ('queued', 'running', 'waiting_approval', "
            "'completed', 'failed', 'cancelled')",
            name="ck_orchestration_runs_status",
        ),
        CheckConstraint("revision > 0", name="ck_orchestration_runs_revision"),
        CheckConstraint(
            "total_steps > 0", name="ck_orchestration_runs_total_steps"
        ),
        CheckConstraint(
            "completed_steps >= 0 AND completed_steps <= total_steps",
            name="ck_orchestration_runs_completed_steps",
        ),
        CheckConstraint(
            "max_turns > 0", name="ck_orchestration_runs_max_turns"
        ),
        Index("ix_orchestration_runs_status", "status", "created_at"),
        Index("ix_orchestration_runs_owner_id", "owner_id"),
        Index("ix_orchestration_runs_agent_id", "agent_id"),
        Index("ix_orchestration_runs_session_id", "session_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    task: Mapped[str] = mapped_column(Text, nullable=False)
    agent_ids: Mapped[list] = mapped_column(JSONB, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    revision: Mapped[int] = mapped_column(Integer, default=1)
    allow_high_tools: Mapped[bool] = mapped_column(Boolean, default=False)
    current_job_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    owner_id: Mapped[str] = mapped_column(String(100), nullable=True)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=True)
    session_id: Mapped[str] = mapped_column(String(50), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(200), nullable=True)
    result: Mapped[object] = mapped_column(JSONB, nullable=True)
    error_type: Mapped[str] = mapped_column(String(200), nullable=True)
    total_steps: Mapped[int] = mapped_column(Integer, nullable=False)
    completed_steps: Mapped[int] = mapped_column(Integer, default=0)
    max_turns: Mapped[int] = mapped_column(Integer, default=1)
    approved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    cancelled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class OrchestrationStep(Base):

    __tablename__ = "orchestration_steps"
    __table_args__ = (
        UniqueConstraint(
            "run_id", "position", name="uq_orchestration_steps_position"
        ),
        CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', "
            "'cancelled', 'skipped')",
            name="ck_orchestration_steps_status",
        ),
        CheckConstraint("position >= 0", name="ck_orchestration_steps_position"),
        CheckConstraint(
            "attempt_count >= 0", name="ck_orchestration_steps_attempt_count"
        ),
        CheckConstraint(
            "max_attempts > 0", name="ck_orchestration_steps_max_attempts"
        ),
        Index("ix_orchestration_steps_run_status", "run_id", "status"),
        Index("ix_orchestration_steps_agent_id", "agent_id"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    run_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orchestration_runs.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    agent_id: Mapped[str] = mapped_column(String(50), nullable=False)
    turn: Mapped[int] = mapped_column(Integer, nullable=True)
    depends_on_step_id: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("orchestration_steps.id", ondelete="SET NULL"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    input_text: Mapped[str] = mapped_column(Text, nullable=True)
    result_text: Mapped[str] = mapped_column(Text, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=2)
    error_type: Mapped[str] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    finished_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
