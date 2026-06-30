from sqlalchemy import (
    Integer,
    String,
    Text,
    DateTime
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column
)

from datetime import datetime, timezone

from database.base import Base

from pgvector.sqlalchemy import Vector

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
        Vector(768),
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
        nullable=True
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
        Vector(768),
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