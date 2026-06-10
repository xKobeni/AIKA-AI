import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from llm.embedding_service import EmbeddingService

embedder = EmbeddingService()

vector = embedder.generate_embedding(
    "AIKA is built with Python"
)

print("Vector Length:", len(vector))
print("First 10 Values:", vector[:10])