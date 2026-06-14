import time
from datetime import datetime


class ChatHandler:

    def __init__(
        self,
        conversation_repo,
        llm,
        memory_extractor,
        context_manager,
        tool_manager=None
    ):

        self.conversation_repo = conversation_repo
        self.llm = llm
        self.memory_extractor = memory_extractor
        self.context_manager = context_manager
        self.tool_manager = tool_manager

    def _should_search_web(self, user_message):

        if not self.tool_manager:
            return False

        text = user_message.lower().strip()

        # Skip for greetings
        if text.rstrip("?!.,") in {
            "hello", "hi", "hey", "how are you",
            "good morning", "good afternoon", "good evening",
            "what's up", "sup", "yo"
        }:
            return False

        # Skip for memory/personal queries
        if any(p in text for p in [
            "my ", "mine ", "remember ",
            "what do you know", "tell me about me",
            "what is my", "what are my",
            "what projects", "what project",
            "my goals", "my goal", "my plans", "my plan",
            "my favorite", "my preferences",
        ]):
            return False

        # Time-sensitive topics -> search
        if any(p in text for p in [
            "weather", "news", "forecast", "current ",
            "latest", "recent", "this year",
            "2025", "2026", "2027",
        ]):
            return True

        # General question words -> search
        if any(text.startswith(q) for q in [
            "what", "who", "where", "when", "why", "how",
        ]):
            return True

        return False

    def chat(self, user_message):

        t_chat = time.time()

        # -------------------------
        # Save User Message
        # -------------------------
        self.conversation_repo.create(
            role="user",
            content=user_message
        )

        # -------------------------
        # Build Context
        # -------------------------
        t0 = time.time()
        context = (
            self.context_manager
            .build_context(user_message)
        )
        t_context = time.time() - t0

        memory_context = (
            context["memory_context"]
        )

        conversation_context = (
            context["conversation_context"]
        )

        if conversation_context.strip():
            conversation_block = (
                f"Recent Conversation:\n"
                f"{conversation_context}"
            )
        else:
            conversation_block = (
                "(No recent conversation history)"
            )

        # -------------------------
        # Reflexive Web Search
        # -------------------------
        web_results_block = ""
        n_results = 0
        t0 = time.time()

        if self._should_search_web(user_message):

            search_query = user_message

            if conversation_context.strip():
                last_turn = conversation_context.strip().split("\n")[-1]
                search_query = (
                    f"{last_turn} {user_message}"
                )

            search_result = (
                self.tool_manager.execute_tool(
                    "web_search",
                    query=search_query,
                    max_results=5
                )
            )

            results = (
                search_result.get("results", [])
                if isinstance(search_result, dict)
                else []
            )
            n_results = len(results)

            if results:

                lines = []

                for r in results:

                    lines.append(
                        f"- {r.get('title', '')}\n"
                        f"  {r.get('body', r.get('snippet', ''))}"
                    )

                web_results_block = (
                    "Web Search Results:\n"
                    + "\n\n".join(lines)
                )

        t_web = time.time() - t0

        # -------------------------
        # Build Prompt
        # -------------------------
        now = datetime.now()
        time_str = now.strftime("%H:%M")
        date_str = now.strftime("%A, %B %d, %Y")

        prompt = f"""
            You are AIKA, a memory-augmented AI assistant.

            Current time: {time_str}
            Current date: {date_str}

            Known Memories:
            {memory_context}

            {conversation_block}

            {web_results_block}

            User:
            {user_message}

            RULES:
            - The current time and date above are the real actual values. Use them exactly.
            - When asked about the time, say something like "It's {time_str}."
            - Never change or reformat the time. Never add AM/PM to 24-hour time.
            - Use Known Memories and Web Search Results if available.
            - If Web Search Results are provided, use them to answer.
            - Never say you searched the web unless asked.
            - Never make up information. If you don't know, say so.
            - Respond naturally and maintain context.
            """

        # -------------------------
        # Generate Response
        # -------------------------
        t0 = time.time()
        response = self.llm.generate(
            prompt
        )
        t_llm = time.time() - t0

        # -------------------------
        # Save Assistant Response
        # -------------------------
        self.conversation_repo.create(
            role="assistant",
            content=response
        )

        # -------------------------
        # Trim old conversations
        # -------------------------
        self.conversation_repo.trim()

        # -------------------------
        # Debug Summary
        # -------------------------
        t_total = time.time() - t_chat
        web_status = (
            f"{t_web:.2f}s ({n_results} results)"
            if web_results_block
            else "skipped"
        )
        print(f"[DEBUG]   Context: {t_context:.2f}s | Web: {web_status} | LLM: {t_llm:.2f}s")

        return response
