import sys
from pathlib import Path
from datetime import datetime, timedelta

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from llm.embedding_service import EmbeddingService
from repositories.memory_repository import MemoryRepository
import math

embedder = EmbeddingService()
repo = MemoryRepository()

test_queries = [
    "What project am I building?",
    "What do you know about me?",
    "Tell me about my goals",
    "What are my preferences?",
    "General chat about anything"
]

for query in test_queries:
    print(f"\n{'='*60}")
    print(f"QUERY: {query}")
    print(f"{'='*60}")

    query_embedding = embedder.generate_embedding(query)
    if not query_embedding:
        print("[SKIP] Embedding failed")
        continue

    results = repo.semantic_search(query_embedding, limit=8)

    if not results:
        print("No results found.")
        continue

    header = (
        f"{'Score':<8} {'Sim*0.5':<10} {'Imp*0.25':<11} "
        f"{'LogAcc*0.1':<11} {'Boost':<7} {'Rec*0.15':<10} "
        f"{'Cat':<12} {'Imp':<4} {'Acc':<4} Content"
    )
    print(header)
    print("-" * 120)

    for m in results:
        emb = embedder.generate_embedding(query)
        sim = repo.cosine_similarity(emb, m.embedding) if emb else 0

        ref_time = m.last_accessed or m.created_at
        if ref_time:
            hrs = (datetime.utcnow() - ref_time).total_seconds() / 3600
            rec = math.exp(-hrs / 720.0)
        else:
            rec = 0.0

        cat_boost = {"project": 0.3, "goal": 0.2, "skill": 0.1}.get(m.category, 0)

        sim_part = sim * 0.50
        imp_part = (m.importance / 10.0) * 0.25
        acc_part = math.log(1 + m.access_count) * 0.10
        rec_part = rec * 0.15
        total = getattr(m, '_score', 0)

        print(
            f"{total:<8.4f} {sim_part:<10.4f} {imp_part:<11.4f} "
            f"{acc_part:<11.4f} {cat_boost:<7.2f} {rec_part:<10.4f} "
            f"{m.category:<12} {m.importance:<4} {m.access_count:<4} {m.content[:50]}"
        )

print("\nDone.")
