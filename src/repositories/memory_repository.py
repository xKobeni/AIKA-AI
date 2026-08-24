from database.db import db_session
from database.embedding_compatibility import validate_embedding_vector
from database.models import Memory, EMBEDDING_DIMENSION
from sqlalchemy import func
from datetime import datetime, timezone
import math
import numpy as np
from config.settings import settings

class MemoryRepository:

    def create(self, memory_type, content, embedding, category="fact",
               importance=5, profile_score=0, source_conversation_id=None,
               agent_id=None):

        validate_embedding_vector(
            embedding,
            EMBEDDING_DIMENSION,
            name="memory embedding",
        )

        with db_session() as db:

            memory = Memory(
                type=memory_type,
                content=content,
                embedding=embedding,
                category=category,
                importance=importance,
                profile_score=profile_score,
                source_conversation_id=source_conversation_id,
                agent_id=agent_id
            )

            db.add(memory)
            db.flush()
            db.refresh(memory)

            return memory
    
    # Get memories by category
    def get_by_category(self, category, agent_id=None):

        with db_session() as db:

            query = db.query(Memory).filter(Memory.category == category)
            if agent_id:
                query = query.filter(
                    (Memory.agent_id == agent_id) | (Memory.agent_id.is_(None))
                )
            return query.all()

    def get_by_categories(self, categories, agent_id=None):

        with db_session() as db:

            query = db.query(Memory).filter(Memory.category.in_(categories))
            if agent_id:
                query = query.filter(
                    (Memory.agent_id == agent_id) | (Memory.agent_id.is_(None))
                )
            return query.all()

    def get_top_profile_memories(
        self,
        categories,
        max_per_category,
        agent_id=None,
    ):
        """Return a database-bounded profile selection for each category."""
        categories = list(dict.fromkeys(categories or []))
        max_per_category = int(max_per_category)
        if not categories or max_per_category <= 0:
            return []

        with db_session() as db:
            return self._top_profile_query(
                db,
                categories,
                max_per_category,
                agent_id=agent_id,
            ).all()

    @staticmethod
    def _top_profile_query(
        db,
        categories,
        max_per_category,
        agent_id=None,
    ):
        ranked = db.query(
            Memory.id.label("memory_id"),
            func.row_number().over(
                partition_by=Memory.category,
                order_by=(
                    Memory.profile_score.desc(),
                    Memory.importance.desc(),
                    Memory.access_count.desc(),
                    Memory.id.desc(),
                ),
            ).label("category_rank"),
        ).filter(Memory.category.in_(categories))
        if agent_id:
            ranked = ranked.filter(
                (Memory.agent_id == agent_id)
                | (Memory.agent_id.is_(None))
            )

        ranked = ranked.subquery()
        return (
            db.query(Memory)
            .join(ranked, Memory.id == ranked.c.memory_id)
            .filter(ranked.c.category_rank <= max_per_category)
            .order_by(Memory.category, ranked.c.category_rank)
        )

    # Memory retrieval methods
    def get_all(self, agent_id=None):

        with db_session() as db:

            query = db.query(Memory).order_by(Memory.id)
            if agent_id:
                query = query.filter(
                    (Memory.agent_id == agent_id) | (Memory.agent_id.is_(None))
                )
            return query.all()


    # Search memories by content
    def search(self, query, agent_id=None):

        with db_session() as db:

            q = db.query(Memory).filter(
                Memory.content.ilike(f"%{query}%")
            )
            if agent_id:
                q = q.filter(
                    (Memory.agent_id == agent_id) | (Memory.agent_id.is_(None))
                )
            return q.all()

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

        self.batch_update_profile_scores({memory_id: score})

    def batch_update_profile_scores(self, score_by_id):
        """Persist profile scores in one transaction."""
        mappings = [
            {"id": memory_id, "profile_score": score}
            for memory_id, score in dict(score_by_id or {}).items()
            if memory_id is not None
        ]
        if not mappings:
            return 0

        with db_session() as db:
            db.bulk_update_mappings(Memory, mappings)
        return len(mappings)
        
    def semantic_search(
        self,
        query_embedding,
        limit=None,
        min_score=None,
        agent_id=None,
        candidate_multiplier=None,
    ):

        validate_embedding_vector(
            query_embedding,
            EMBEDDING_DIMENSION,
            name="memory query embedding",
        )

        if limit is None:
            limit = settings.memory_retrieval_limit
        if min_score is None:
            min_score = settings.memory_min_score

        with db_session() as db:

            if candidate_multiplier is None:
                candidate_multiplier = settings.memory_candidate_multiplier
            candidate_limit = limit * max(1, candidate_multiplier)

            query = (
                db.query(Memory)
                .filter(Memory.embedding.isnot(None))
            )
            if agent_id:
                query = query.filter(
                    (Memory.agent_id == agent_id) | (Memory.agent_id.is_(None))
                )

            candidates = (
                query
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
                elif memory.category == "person":
                    category_boost = 0.15
                elif memory.category == "decision":
                    category_boost = 0.2
                elif memory.category == "outcome":
                    category_boost = 0.1

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

        return self.batch_update_access([memory_id])

    def batch_update_access(self, memory_ids):
        """Update access metadata for all selected memories in one query."""
        unique_ids = list(dict.fromkeys(
            memory_id for memory_id in (memory_ids or [])
            if memory_id is not None
        ))
        if not unique_ids:
            return 0

        with db_session() as db:
            return (
                db.query(Memory)
                .filter(Memory.id.in_(unique_ids))
                .update(
                    {
                        Memory.access_count: Memory.access_count + 1,
                        Memory.last_accessed: datetime.now(timezone.utc),
                    },
                    synchronize_session=False,
                )
            )
