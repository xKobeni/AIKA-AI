from database.base import Base
from database.db import engine
from database.models import Memory

Base.metadata.create_all(
    bind=engine
)

print("Tables created.")