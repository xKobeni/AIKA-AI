class ChatHandler:

    def __init__(
        self,
        memory_repo,
        conversation_repo,
        embedding_service,
        llm,
        memory_extractor
    ):

        self.memory_repo = memory_repo
        self.conversation_repo = conversation_repo
        self.embedding_service = embedding_service
        self.llm = llm
        self.memory_extractor = memory_extractor

    def chat(self, user_message):

        # -------------------------
        # Save User Message
        # -------------------------
        self.conversation_repo.create(
            role="user",
            content=user_message
        )

        # -------------------------
        # Generate Embedding
        # -------------------------
        query_embedding = self.embedding_service.generate_embedding(
            user_message
        )

        # -------------------------
        # Extract Memory (AUTO MEMORY SYSTEM)
        # -------------------------
        result = self.memory_extractor.extract_memory(user_message)

        if result:
            print("[Memory Stored] ->", result)

        # -------------------------
        # Load Relevant Memories (SEMANTIC SEARCH)
        # -------------------------
        memories = self.memory_repo.semantic_search(
            query_embedding,
            limit=5
        )

        # -------------------------
        # UPDATE MEMORY USAGE (IMPORTANT FOR INTELLIGENCE)
        # -------------------------
        for memory in memories:
            self.memory_repo.update_access(memory.id)

        # -------------------------
        # Build Memory Context
        # -------------------------
        memory_context = "\n".join([
            f"- {memory.content}"
            for memory in memories
        ])

        # -------------------------
        # Load Recent Conversations
        # -------------------------
        conversations = self.conversation_repo.get_recent(10)

        conversation_context = "\n".join([
            f"{c.role}: {c.content}"
            for c in conversations
        ])

        # -------------------------
        # Build Prompt
        # -------------------------
        prompt = f"""
            You are AIKA, a memory-augmented AI assistant.

            Known Memories:
            {memory_context}

            Recent Conversation:
            {conversation_context}

            User:
            {user_message}

            Respond naturally and maintain context.
            """

        # -------------------------
        # Generate Response
        # -------------------------
        response = self.llm.generate(prompt)

        # -------------------------
        # Save Assistant Response
        # -------------------------
        self.conversation_repo.create(
            role="assistant",
            content=response
        )

        return response