class ChatHandler:

    def __init__(
        self,
        conversation_repo,
        llm,
        memory_extractor,
        context_manager
    ):

        self.conversation_repo = conversation_repo
        self.llm = llm
        self.memory_extractor = memory_extractor
        self.context_manager = context_manager

    def chat(self, user_message):
        
        print(type(self.conversation_repo))

        # -------------------------
        # Save User Message
        # -------------------------
        self.conversation_repo.create(
            role="user",
            content=user_message
        )

        # -------------------------
        # Auto Memory Extraction
        # -------------------------
        result = self.memory_extractor.extract_memory(
            user_message
        )

        if result:
            print(
                "[Memory Stored] ->",
                result
            )

        # -------------------------
        # Build Context
        # -------------------------
        context = (
            self.context_manager
            .build_context(user_message)
        )

        memory_context = (
            context["memory_context"]
        )

        conversation_context = (
            context["conversation_context"]
        )

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
        response = self.llm.generate(
            prompt
        )

        # -------------------------
        # Save Assistant Response
        # -------------------------
        self.conversation_repo.create(
            role="assistant",
            content=response
        )

        return response