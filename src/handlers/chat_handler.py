import time
import logging
from datetime import datetime

from config.settings import settings

logger = logging.getLogger(__name__)


class ChatHandler:

    def __init__(
        self,
        conversation_repo,
        llm,
        memory_extractor,
        context_manager,
        tool_manager=None,
        session_id=None,
        embedding_service=None,
        session_repo=None,
        model_router=None
    ):

        self.conversation_repo = conversation_repo
        self.llm = llm
        self.memory_extractor = memory_extractor
        self.context_manager = context_manager
        self.tool_manager = tool_manager
        self.session_id = session_id
        self.embedding_service = embedding_service
        self.session_repo = session_repo
        self.model_router = model_router
        self.log_level = settings.log_level

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

        # Skip self-referential questions about AIKA
        if any(p in text for p in [
            "what are you", "who are you", "what is your name",
            "tell me about yourself", "what do you do",
        ]):
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

    def chat(self, user_message, intent=None, tool_name=None):

        t_chat = time.time()

        # -------------------------
        # Input Validation
        # -------------------------
        if len(user_message) > settings.max_input_length:
            return (
                f"Message too long ({len(user_message)} chars). "
                f"Maximum is {settings.max_input_length} characters."
            )

        # -------------------------
        # Generate Embeddings for User Message
        # -------------------------
        user_embedding = None
        if self.embedding_service:
            try:
                user_embedding = (
                    self.embedding_service
                    .generate_embedding(user_message)
                )
            except Exception:
                logger.debug("Failed to generate user embedding", exc_info=True)

        # -------------------------
        # Save User Message
        # -------------------------
        user_conversation = self.conversation_repo.create(
            role="user",
            content=user_message,
            session_id=self.session_id,
            embedding=user_embedding,
            intent=intent,
            tool_used=tool_name
        )

        self._last_user_conv_id = user_conversation.id

        # -------------------------
        # Build Context
        # -------------------------
        t0 = time.time()
        context = (
            self.context_manager
            .build_context(
                user_message,
                session_id=self.session_id
            )
        )
        t_context = time.time() - t0

        memory_context = (
            context["memory_context"]
        )

        conversation_context = (
            context["conversation_context"]
        )

        cross_session_context = context.get(
            "cross_session_context", ""
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

        if cross_session_context.strip():
            cross_session_block = (
                f"Relevant Past Discussions:\n"
                f"{cross_session_context}"
            )
        else:
            cross_session_block = ""

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
                    max_results=settings.web_search_max_results
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

        persona = settings.load_persona()

        prompt = f"""{persona}

Current time: {time_str}
Current date: {date_str}

Known Memories:
{memory_context}

{conversation_block}

{cross_session_block}

{web_results_block}

User:
{user_message}

Speak with warmth and emotion. Be conversational — use casual language, express feelings, and let your personality show."""

        # -------------------------
        # Generate Response
        # -------------------------
        t0 = time.time()
        use_model = None
        if self.model_router:
            use_model = self.model_router.select(user_message, task_type="chat")
        response = self.llm.generate_with_model(
            prompt,
            model=use_model
        )
        t_llm = time.time() - t0

        # -------------------------
        # Metrics
        # -------------------------
        full_prompt = prompt.strip()
        prompt_tokens = max(1, len(full_prompt.split()) * 3 // 2)
        response_tokens = max(1, len(response.split()) * 3 // 2)
        response_time_ms = int((time.time() - t_chat) * 1000)

        # -------------------------
        # Generate Embedding for Response
        # -------------------------
        response_embedding = None
        if self.embedding_service:
            try:
                response_embedding = (
                    self.embedding_service
                    .generate_embedding(response)
                )
            except Exception:
                logger.debug("Failed to generate response embedding", exc_info=True)

        # -------------------------
        # Save Assistant Response
        # -------------------------
        self.conversation_repo.create(
            role="assistant",
            content=response,
            session_id=self.session_id,
            embedding=response_embedding,
            intent=intent,
            tool_used=tool_name,
            model_used=settings.chat_model,
            response_time_ms=response_time_ms,
            token_count=response_tokens
        )

        # -------------------------
        # Update Session Tracking
        # -------------------------
        if self.session_repo and self.session_id:
            self.session_repo.increment_message_count(self.session_id, 2)
            self.session_repo.update_last_active(self.session_id)

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
        logger.debug(
            "Context: %.2fs | Web: %s | LLM: %.2fs | Prompt tokens: ~%d | Response tokens: ~%d | Total: %.2fs",
            t_context, web_status, t_llm, prompt_tokens, response_tokens, t_total
        )

        return response
