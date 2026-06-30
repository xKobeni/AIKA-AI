import time
import logging

from config.settings import settings

logger = logging.getLogger(__name__)


def _count_tokens(text):
    if not text:
        return 0
    words = len(text.split())
    return int(words * 1.3) + 1


class ContextManager:

    def __init__(
        self,
        memory_repo,
        conversation_repo,
        embedding_service,
        retrieval_service=None
    ):
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.max_context_tokens = settings.max_context_tokens
        self.retrieval_limit = settings.memory_retrieval_limit
        self.recent_count = settings.recent_conversations_count

    def build_context(
        self,
        user_message,
        session_id=None
    ):

        t0 = time.time()

        # -------------------------
        # Retrieve Memories
        # -------------------------

        memories = []

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                user_message,
                limit=self.retrieval_limit
            )

            if isinstance(result, str):
                result = []

            memories = result

        else:

            query_embedding = (
                self.embedding_service
                .generate_embedding(user_message)
            )

            memories = (
                self.memory_repo
                .semantic_search(
                    query_embedding,
                    limit=self.retrieval_limit + 2
                )
            )

            memories = [
                m for m in memories
                if getattr(m, '_score', 0) >= settings.memory_min_score
            ]

            memories = memories[:self.retrieval_limit]

        # -------------------------
        # Update Access Tracking
        # -------------------------

        for memory in memories:

            self.memory_repo.update_access(
                memory.id
            )

        # -------------------------
        # Build Structured Sections
        # -------------------------

        sections = []

        # Profile section
        t1 = time.time()

        if self.retrieval_service:

            profile_text = (
                self.retrieval_service.profile_builder
                .build_profile(max_per_category=settings.max_profile_per_category)
            )

            if profile_text:
                sections.append(
                    ("USER PROFILE", profile_text)
                )

        t_profile = time.time() - t1

        # Top memories grouped by category
        if memories:

            by_category = {}

            for m in memories:
                by_category.setdefault(
                    m.category, []
                ).append(m)

            cat_blocks = []

            for cat, mems in by_category.items():
                label = cat.upper()
                items = "\n".join(
                    f"  - {m.content}"
                    for m in mems[:2]
                )
                cat_blocks.append(
                    f"{label}:\n{items}"
                )

            sections.append(
                ("RELEVANT MEMORIES",
                 "\n\n".join(cat_blocks))
            )

        # -------------------------
        # Token Budgeting
        # -------------------------

        memory_parts = []
        token_count = 0

        for label, text in sections:
            part = f"=== {label} ===\n{text}"
            estimated = _count_tokens(part)

            if token_count + estimated > self.max_context_tokens:
                break

            memory_parts.append(part)
            token_count += estimated

        memory_context = "\n\n".join(memory_parts)

        t_total = time.time() - t0

        logger.debug(
            "Context: %.2fs profile=%.2fs memories=%d",
            t_total, t_profile, len(memories)
        )

        # -------------------------
        # Recent Conversations
        # -------------------------

        if session_id:
            conversations = (
                self.conversation_repo
                .get_by_session(session_id, self.recent_count)
            )
        else:
            conversations = (
                self.conversation_repo
                .get_recent(self.recent_count)
            )

        conversation_context = "\n".join([
            f"{c.role}: {c.content}"
            for c in conversations
        ])

        return {
            "memory_context": memory_context,
            "conversation_context": conversation_context
        }