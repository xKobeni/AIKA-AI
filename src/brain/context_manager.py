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

    def build_context(
        self,
        user_message
    ):

        # -------------------------
        # Retrieve Memories
        # -------------------------

        memories = []

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                user_message,
                limit=5
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
                    limit=10
                )
            )

            memories = [
                m for m in memories
                if getattr(m, '_score', 0) >= 0.35
            ]

            memories = memories[:5]

        # -------------------------
        # Update Access Tracking
        # -------------------------

        for memory in memories:

            self.memory_repo.update_access(
                memory.id
            )

        # -------------------------
        # Memory Context
        # -------------------------

        memory_context = "\n".join([
            f"- {memory.content}"
            for memory in memories
        ])

        # -------------------------
        # Recent Conversations
        # -------------------------

        conversations = (
            self.conversation_repo
            .get_recent(10)
        )

        conversation_context = "\n".join([
            f"{c.role}: {c.content}"
            for c in conversations
        ])

        return {
            "memory_context": memory_context,
            "conversation_context": conversation_context
        }