from database.base import Base
from database.db import engine
from database.models import (
    Conversation,
    Job,
    JobEvent,
    Memory,
    OrchestrationRun,
    OrchestrationStep,
    Reminder,
    ReminderOccurrence,
    Session,
)
from database.migrations import validate_embedding_schema

Base.metadata.create_all(
    bind=engine
)

with engine.connect() as connection:
    validate_embedding_schema(connection)

print("Tables created and embedding dimensions validated.")
