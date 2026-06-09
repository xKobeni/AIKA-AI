class ContextManager:

    def __init__(
        self,
        memory_repo,
        conversation_repo,
        embedding_service
    ):
        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.embedding_service = embedding_service

    def build_context(
        self,
        user_message
    ):

        # -------------------------
        # Generate Query Embedding
        # -------------------------

        query_embedding = (
            self.embedding_service
            .generate_embedding(user_message)
        )

        # -------------------------
        # Retrieve Memories
        # -------------------------

        memories = (
            self.memory_repo
            .semantic_search(
                query_embedding,
                limit=5
            )
        )

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