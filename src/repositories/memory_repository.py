from database.db import SessionLocal
from database.models import Memory
from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from datetime import datetime
import numpy as np

class MemoryRepository:

    # Create a new memory entry
    def create(self, memory_type, content, embedding, category="fact"):

        db = SessionLocal()

        memory = Memory(
            type=memory_type,
            content=content,
            embedding=embedding,
            category=category
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
        limit=5
    ):

        db = SessionLocal()

        memories = db.query(Memory).all()

        db.close()

        results = []

        for memory in memories:

            if memory.embedding is None:
                continue
            
            similarity = self.cosine_similarity(
                query_embedding,
                memory.embedding
            )

            score = (
                similarity +
                (memory.importance * 0.2) +
                (memory.access_count * 0.1)
            )

            results.append((memory, score))

        results.sort(
            key=lambda x: x[1],
            reverse=True
        )

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