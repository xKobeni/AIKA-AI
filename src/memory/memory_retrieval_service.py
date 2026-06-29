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
        limit=5
    ):

        if not query:
            return []

        t0 = time.time()

        intent = self.intent_analyzer.detect_intent(query)

        if intent == MemoryIntent.PROFILE:
            return self.retrieve_profile()

        t1 = time.time()
        query_embedding = (
            self.embedding_service
            .generate_embedding(query)
        )
        t_embed = time.time() - t1

        t2 = time.time()
        memories = self.memory_repo.semantic_search(
            query_embedding,
            limit=settings.memory_retrieval_limit * settings.memory_candidate_multiplier
        )
        t_search = time.time() - t2

        t3 = time.time()
        memories = self.ranker.filter_by_intent(
            memories,
            intent
        )

        ranked = self.ranker.rank(memories, intent)

        diverse = self.ranker.apply_diversity(ranked)
        t_rank = time.time() - t3

        result = diverse[:limit]

        logger.debug(
            "Retrieval: embed=%.2fs search=%.2fs rank=%.2fs memories=%d",
            t_embed, t_search, t_rank, len(result)
        )

        return result

    def retrieve_profile(self):

        return self.profile_builder.build_profile()
