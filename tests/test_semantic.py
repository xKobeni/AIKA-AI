import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from llm.embedding_service import (
    EmbeddingService
)

from repositories.memory_repository import (
    MemoryRepository
)

embedder = EmbeddingService()

repo = MemoryRepository()

query = (
    "What language is AIKA built with?"
)

query_embedding = (
    embedder.generate_embedding(
        query
    )
)

results = repo.semantic_search(
    query_embedding
)

for memory in results:
    print(memory.content)