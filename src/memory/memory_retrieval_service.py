import time
import logging

from config.settings import settings
from memory.memory_intent import (
    MemoryIntent,
    MemoryIntentAnalyzer
)
from memory.memory_ranker import MemoryRanker
from memory.memory_profile import MemoryProfileBuilder

logger = logging.getLogger(__name__)


class MemoryRetrievalService:

    def __init__(
        self,
        memory_repo,
        embedding_service,
        intent_analyzer=None,
        ranker=None,
        profile_builder=None
    ):

        self.memory_repo = memory_repo
        self.embedding_service = embedding_service
        self.intent_analyzer = (
            intent_analyzer or MemoryIntentAnalyzer()
        )
        self.ranker = ranker or MemoryRanker()
        self.profile_builder = (
            profile_builder
            or MemoryProfileBuilder(memory_repo)
        )

    def retrieve(
        self,
        query,
        limit=5,
        agent_id=None,
        query_embedding=None,
    ):

        if not query:
            return []

        t0 = time.time()

        intent = self.intent_analyzer.detect_intent(query)

        if intent == MemoryIntent.PROFILE:
            return self.retrieve_profile(agent_id=agent_id)

        t1 = time.time()
        if query_embedding is None:
            query_embedding = (
                self.embedding_service
                .generate_embedding(query)
            )
        t_embed = time.time() - t1

        if query_embedding is None:
            logger.warning(
                "Memory retrieval skipped because no query embedding was available."
            )
            return []

        t2 = time.time()
        memories = self.memory_repo.semantic_search(
            query_embedding,
            limit=limit * settings.memory_candidate_multiplier,
            agent_id=agent_id,
            candidate_multiplier=1,
        )
        t_search = time.time() - t2

        t3 = time.time()
        memories = self.ranker.filter_by_intent(
            memories,
            intent
        )

        profile_updates = {}
        for memory in memories:
            profile_score = self._compute_profile_score(memory)
            if profile_score != memory.profile_score:
                profile_updates[memory.id] = profile_score
                memory.profile_score = profile_score

        if profile_updates:
            self.memory_repo.batch_update_profile_scores(profile_updates)

        ranked = self.ranker.rank(memories, intent)

        diverse = self.ranker.apply_diversity(ranked)
        t_rank = time.time() - t3

        result = diverse[:limit]

        logger.debug(
            "Retrieval: embed=%.2fs search=%.2fs rank=%.2fs memories=%d",
            t_embed, t_search, t_rank, len(result)
        )

        return result

    def _compute_profile_score(self, memory):
        score = 0

        if memory.category in ("project", "goal"):
            score += 3
        elif memory.category in ("skill", "person", "decision"):
            score += 2
        elif memory.category in ("preference", "outcome"):
            score += 1

        if memory.access_count >= 5:
            score += 2
        elif memory.access_count >= 2:
            score += 1

        if memory.importance >= 8:
            score += 2
        elif memory.importance >= 6:
            score += 1

        return min(score, 10)

    def retrieve_profile(self, agent_id=None):

        return self.profile_builder.build_profile(agent_id=agent_id)
