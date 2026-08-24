import time
import logging

from config.settings import settings
from brain.prompt_budgeter import count_tokens as _count_tokens

logger = logging.getLogger(__name__)


class ContextManager:

    def __init__(
        self,
        memory_repo,
        conversation_repo,
        embedding_service,
        retrieval_service=None,
        session_repo=None
    ):
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.session_repo = session_repo
        self.max_context_tokens = settings.max_context_tokens
        self.retrieval_limit = settings.memory_retrieval_limit
        self.recent_count = settings.recent_conversations_count
        self.summaries_count = settings.context_session_summaries_count
        self.cross_session_count = settings.context_cross_session_conversations

    def refresh_from_settings(self):
        self.max_context_tokens = settings.max_context_tokens
        self.retrieval_limit = settings.memory_retrieval_limit
        self.recent_count = settings.recent_conversations_count
        self.summaries_count = settings.context_session_summaries_count
        self.cross_session_count = settings.context_cross_session_conversations

    def build_context(
        self,
        user_message,
        session_id=None,
        agent_id=None,
        query_embedding=None,
    ):

        t0 = time.time()

        if query_embedding is None:
            try:
                query_embedding = self.embedding_service.generate_embedding(
                    user_message
                )
            except Exception:
                logger.debug("Context embedding generation failed", exc_info=True)
                query_embedding = None

        # -------------------------
        # Retrieve Memories
        # -------------------------

        memories = []

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                user_message,
                limit=self.retrieval_limit,
                agent_id=agent_id,
                query_embedding=query_embedding,
            )

            if isinstance(result, str):
                result = []

            memories = result

        else:

            if query_embedding is not None:
                memories = (
                    self.memory_repo
                    .semantic_search(
                        query_embedding,
                        limit=self.retrieval_limit + 2,
                        agent_id=agent_id
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

        memory_ids = [memory.id for memory in memories]
        if memory_ids:
            self.memory_repo.batch_update_access(memory_ids)

        # -------------------------
        # Build Structured Sections
        # -------------------------

        sections = []

        # Profile section
        t1 = time.time()

        if self.retrieval_service:

            profile_text = (
                self.retrieval_service.profile_builder
                .build_profile(max_per_category=settings.max_profile_per_category, agent_id=agent_id)
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
        # Session Summaries (cross-session)
        # -------------------------

        past_sessions = []
        if self.session_repo and self.summaries_count > 0:

            past_sessions = self.session_repo.get_recent_with_summaries(
                limit=self.summaries_count,
                exclude_session_id=session_id,
                agent_id=agent_id
            ) or []

            if past_sessions:
                summary_lines = []
                for s in past_sessions:
                    date_str = s.started_at.strftime("%Y-%m-%d")
                    summary = s.summary.strip()
                    if len(summary) > 150:
                        summary = summary[:150] + "..."
                    summary_lines.append(f"- {date_str}: {summary}")

                sections.append(
                    ("RECENT SESSIONS",
                     "\n".join(summary_lines))
                )

        # -------------------------
        # Cross-Session Conversations
        # -------------------------

        cross_session_context = ""
        past_conversations = []

        if (self.session_repo
                and self.conversation_repo
                and self.cross_session_count > 0
                and session_id):

            try:
                if query_embedding is not None:
                    past_conversations = (
                        self.conversation_repo
                        .search_across_sessions(
                            query_embedding,
                            current_session_id=session_id,
                            limit=self.cross_session_count,
                            agent_id=agent_id
                        )
                    )
                    past_conversations = past_conversations or []

                if past_conversations:
                    lines = []
                    for c in past_conversations:
                        role = "User" if c.role == "user" else "AIKA"
                        content = c.content[:200]
                        if len(c.content) > 200:
                            content += "..."
                        lines.append(f"[{role}]: {content}")

                    cross_session_context = "\n".join(lines)

            except Exception as e:
                logger.debug(
                    "Cross-session search failed: %s", e
                )

        # -------------------------
        # Complete prompt budgeting is applied after persona, grounding,
        # conversation history, tool results, and the user request are assembled.
        # Do not stop at the first oversized memory section here because doing so
        # would discard every later section before the shared budgeter can rank it.
        # -------------------------

        memory_context = "\n\n".join(
            f"=== {label} ===\n{text}"
            for label, text in sections
        )

        t_total = time.time() - t0

        logger.debug(
            "Context: %.2fs profile=%.2fs memories=%d sessions=%d past_convs=%d",
            t_total, t_profile, len(memories),
            len(past_sessions) if self.session_repo else 0,
            len(past_conversations) if cross_session_context else 0
        )

        # -------------------------
        # Recent Conversations (current session)
        # -------------------------

        if session_id:
            conversations = (
                self.conversation_repo
                .get_by_session(session_id, self.recent_count, agent_id=agent_id)
            )
        else:
            conversations = (
                self.conversation_repo
                .get_recent(self.recent_count, agent_id=agent_id)
            )

        conversation_context = "\n".join(
            f"{'User' if c.role == 'user' else 'AIKA'}: {c.content}"
            for c in conversations
            if str(getattr(c, "content", "") or "").strip()
        )

        return {
            "memory_context": memory_context,
            "conversation_context": conversation_context,
            "cross_session_context": cross_session_context
        }
