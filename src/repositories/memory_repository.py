from database.db import SessionLocal
from database.models import Memory
from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from datetime import datetime
import math
import numpy as np

class MemoryRepository:

    # Create a new memory entry
    def create(self, memory_type, content, embedding, category="fact", importance=5):

        db = SessionLocal()

        memory = Memory(
            type=memory_type,
            content=content,
            embedding=embedding,
            category=category,
            importance=importance
        )

        db.add(memory)
        db.commit()
        db.refresh(memory)

        db.close()

        return memory
    
    # Get memories by category
    def get_by_category(self, category):

        db = SessionLocal()

        memories = (
            db.query(Memory)
            .filter(Memory.category == category)
            .all()
        )

        db.close()

        return memories

    # Memory retrieval methods
    def get_all(self):

        db = SessionLocal()

        memories = (
            db.query(Memory)
            .order_by(Memory.id)
            .all()
        )

        db.close()

        return memories


    # Search memories by content
    def search(self, query):

        db = SessionLocal()

        memories = (
            db.query(Memory)
            .filter(
                Memory.content.ilike(
                    f"%{query}%"
                )
            )
            .all()
        )

        db.close()

        return memories

    # Delete a memory by ID
    def delete(self, memory_id):

        db = SessionLocal()

        memory = (
            db.query(Memory)
            .filter(
                Memory.id == memory_id
            )
            .first()
        )

        if memory:

            db.delete(memory)
            db.commit()

        db.close()
        
    def semantic_search(
        self,
        query_embedding,
        limit=5,
        min_score=0.3
    ):

        db = SessionLocal()

        candidate_limit = limit * 3

        candidates = (
            db.query(Memory)
            .filter(Memory.embedding.isnot(None))
            .order_by(Memory.embedding.cosine_distance(query_embedding))
            .limit(candidate_limit)
            .all()
        )

        db.close()

        results = []

        for memory in candidates:

            similarity = self.cosine_similarity(
                query_embedding,
                memory.embedding
            )

            # RECENCY DECAY (exponential)
            reference_time = memory.last_accessed or memory.created_at
            if reference_time:
                hours_since = (
                    datetime.utcnow() - reference_time
                ).total_seconds() / 3600
                recency_score = math.exp(-hours_since / 720.0)
            else:
                recency_score = 0.0

            # CATEGORY BOOST
            category_boost = 0

            if memory.category == "project":
                category_boost = 0.3

            elif memory.category == "goal":
                category_boost = 0.2

            elif memory.category == "skill":
                category_boost = 0.1

            score = (
                similarity * 0.50 +
                (memory.importance / 10.0) * 0.25 +
                math.log(1 + memory.access_count) * 0.10 +
                category_boost +
                recency_score * 0.15
            )

            if score < min_score:
                continue

            results.append((memory, score))

        results.sort(key=lambda x: x[1], reverse=True)

        for m in results:
            m[0]._score = m[1]

        return [m[0] for m in results[:limit]]
    
    # Simple cosine similarity implementation
    def cosine_similarity(self, a, b):

        a = np.array(a)
        b = np.array(b)

        denom = (np.linalg.norm(a) * np.linalg.norm(b))

        if denom == 0:
            return 0.0

        return float(np.dot(a, b) / denom)
        
    # Update access count and last accessed time
    def update_access(
        self,
        memory_id
    ):
        
        db = SessionLocal()

        memory = (
            db.query(Memory)
            .filter(
                Memory.id == memory_id
            )
            .first()
        )

        if memory:

            memory.access_count += 1

            memory.last_accessed = (
                datetime.utcnow()
            )

            db.commit()

        db.close()