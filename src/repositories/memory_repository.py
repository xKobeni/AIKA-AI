from database.db import db_session
from database.models import Memory
from pgvector.sqlalchemy import Vector
from sqlalchemy import text
from datetime import datetime, timezone
import math
import numpy as np
from config.settings import settings

class MemoryRepository:

    # Create a new memory entry
    def create(self, memory_type, content, embedding, category="fact", importance=5, profile_score=0):

        with db_session() as db:

            memory = Memory(
                type=memory_type,
                content=content,
                embedding=embedding,
                category=category,
                importance=importance,
                profile_score=profile_score
            )

            db.add(memory)
            db.flush()
            db.refresh(memory)

            return memory
    
    # Get memories by category
    def get_by_category(self, category):

        with db_session() as db:

            memories = (
                db.query(Memory)
                .filter(Memory.category == category)
                .all()
            )

            return memories

    def get_by_categories(self, categories):

        with db_session() as db:

            memories = (
                db.query(Memory)
                .filter(Memory.category.in_(categories))
                .all()
            )

            return memories

    # Memory retrieval methods
    def get_all(self):

        with db_session() as db:

            memories = (
                db.query(Memory)
                .order_by(Memory.id)
                .all()
            )

            return memories


    # Search memories by content
    def search(self, query):

        with db_session() as db:

            memories = (
                db.query(Memory)
                .filter(
                    Memory.content.ilike(
                        f"%{query}%"
                    )
                )
                .all()
            )

            return memories

    # Delete a memory by ID
    def delete(self, memory_id):

        with db_session() as db:

            memory = (
                db.query(Memory)
                .filter(
                    Memory.id == memory_id
                )
                .first()
            )

            if memory:

                db.delete(memory)

    # Update profile score for a memory
    def update_profile_score(
        self,
        memory_id,
        score
    ):

        with db_session() as db:

            memory = (
                db.query(Memory)
                .filter(
                    Memory.id == memory_id
                )
                .first()
            )

            if memory:

                memory.profile_score = score
        
    def semantic_search(
        self,
        query_embedding,
        limit=None,
        min_score=None
    ):

        if limit is None:
            limit = settings.memory_retrieval_limit
        if min_score is None:
            min_score = settings.memory_min_score

        with db_session() as db:

            candidate_limit = limit * settings.memory_candidate_multiplier

            candidates = (
                db.query(Memory)
                .filter(Memory.embedding.isnot(None))
                .order_by(Memory.embedding.cosine_distance(query_embedding))
                .limit(candidate_limit)
                .all()
            )

            results = []

            for memory in candidates:

                similarity = self.cosine_similarity(
                    query_embedding,
                    memory.embedding
                )

                # RECENCY DECAY (exponential)
                now = datetime.now(timezone.utc)
                reference_time = memory.last_accessed or memory.created_at
                if reference_time:
                    if reference_time.tzinfo is None:
                        reference_time = reference_time.replace(tzinfo=timezone.utc)
                    hours_since = (
                        now - reference_time
                    ).total_seconds() / 3600
                    recency_score = math.exp(-hours_since / settings.memory_recency_half_life_hours)
                else:
                    recency_score = 0.0

                # CATEGORY BOOST
                category_boost = 0

                if memory.category == "project":
                    category_boost = settings.memory_category_boost_project
                elif memory.category == "goal":
                    category_boost = settings.memory_category_boost_goal
                elif memory.category == "skill":
                    category_boost = settings.memory_category_boost_skill

                score = (
                    similarity * settings.memory_sim_weight +
                    (memory.importance / 10.0) * settings.memory_importance_weight +
                    (memory.profile_score / 10.0) * settings.memory_profile_weight +
                    math.log(1 + memory.access_count) * settings.memory_access_weight +
                    category_boost +
                    recency_score * settings.memory_recency_weight
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

        with db_session() as db:

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
                    datetime.now(timezone.utc)
                )