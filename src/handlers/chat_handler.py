import time
import logging
from typing import Iterator

from config.settings import settings
from brain.context_manager import _count_tokens
from brain.request_context import RequestContextBuilder
from handlers.response_finalizer import ResponseFinalizer

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
        model_router=None,
        agent_registry=None,
        response_finalizer=None,
        request_context_builder=None,
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
        self.agent_registry = agent_registry
        self.request_context_builder = (
            request_context_builder
            or RequestContextBuilder(
                context_manager,
                agent_registry=agent_registry,
                tool_manager=tool_manager,
            )
        )
        self.response_finalizer = response_finalizer or ResponseFinalizer(
            conversation_repo,
            embedding_service=embedding_service,
            session_repo=session_repo,
        )
        self.log_level = settings.log_level
        self._last_user_conv_id = None
        self.last_response_metadata = None

    @staticmethod
    def _assemble_prompt_sections(
        request_context, user_message, web_results_block
    ):
        sections = list(request_context.prompt_sections())
        if web_results_block.strip():
            sections.append(
                "=== WEB SEARCH RESULTS (use these to answer accurately) ===\n"
                + web_results_block
            )
        sections.append(
            "=== INSTRUCTIONS ===\n"
            "- Respond naturally and warmly.\n"
            "- Only use facts from the sections above — do not fabricate details.\n"
            "- If you are unsure, say so honestly rather than guessing.\n"
            "- Keep your response focused on what the user actually asked."
        )
        sections.append(f"User:\n{user_message}")
        return sections

    def refresh_from_settings(self):
        self.log_level = settings.log_level

    def _get_model_for_agent(self, agent_id=None):
        if agent_id and self.agent_registry:
            profile = self.agent_registry.get(agent_id)
            if profile and profile.model:
                return profile.model
        return None

    @staticmethod
    def _truncate_to_tokens(text, token_limit):
        if token_limit <= 0:
            return ""
        words = text.split()
        if _count_tokens(text) <= token_limit:
            return text
        low, high = 0, len(words)
        while low < high:
            mid = (low + high + 1) // 2
            if _count_tokens(" ".join(words[:mid])) <= token_limit:
                low = mid
            else:
                high = mid - 1
        clipped = " ".join(words[:low]).rstrip()
        return f"{clipped} ..." if clipped else ""

    def _budget_prompt(self, sections):
        """Budget the complete prompt while preserving persona and final request."""
        sections = [section for section in sections if section and section.strip()]
        if not sections:
            return ""

        max_tokens = getattr(self.context_manager, "max_context_tokens", None)
        if not isinstance(max_tokens, int):
            max_tokens = getattr(settings, "max_context_tokens", 6000)
        if not isinstance(max_tokens, int):
            max_tokens = 6000
        max_tokens = max(1, max_tokens)
        required_indexes = {0}
        required_indexes.update(range(max(0, len(sections) - 2), len(sections)))
        selected = {}
        remaining = max_tokens

        required_order = list(range(max(0, len(sections) - 2), len(sections)))
        if 0 not in required_order:
            required_order.append(0)
        for index in required_order:
            separator_cost = 1 if selected else 0
            fitted = self._truncate_to_tokens(
                sections[index], max(0, remaining - separator_cost)
            )
            if fitted:
                selected[index] = fitted
                remaining -= _count_tokens(fitted) + separator_cost

        for index, section in enumerate(sections):
            if index in required_indexes or remaining <= 1:
                continue
            fitted = self._truncate_to_tokens(section, remaining - 1)
            if fitted:
                selected[index] = fitted
                remaining -= _count_tokens(fitted) + 1

        return "\n\n".join(selected[index] for index in sorted(selected))

    def _model_metrics(self, prompt, response, llm_seconds):
        metrics = {}
        get_metrics = getattr(self.llm, "get_last_metrics", None)
        if callable(get_metrics):
            metrics = get_metrics() or {}
        if not isinstance(metrics, dict):
            metrics = {}
        return {
            "prompt_tokens": metrics.get(
                "prompt_tokens", max(1, len(prompt.strip()) // 4)
            ),
            "response_tokens": metrics.get(
                "response_tokens", max(1, len(response) // 4)
            ),
            "response_time_ms": metrics.get(
                "response_time_ms", int(llm_seconds * 1000)
            ),
        }

    def _should_search_web(self, user_message, agent_id=None):

        if not self.tool_manager:
            return False

        if agent_id and self.agent_registry:
            profile = self.agent_registry.get(agent_id)
            if profile and profile.allowed_tools and "web_search" not in profile.allowed_tools:
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
            "what can you do", "how do you work",
        ]):
            return False

        # Skip conversational / emotional questions directed at AIKA
        if any(p in text for p in [
            "how do you feel", "do you think", "do you like",
            "what do you think", "would you say", "can you help",
            "are you okay", "are you there",
        ]):
            return False

        # Skip questions about past conversations or user's own memory
        if any(p in text for p in [
            "what did i", "what did we", "what did you say",
            "do you remember", "did you know", "you said",
            "tell me what i", "what have i", "last time",
        ]):
            return False

        # Skip for memory/personal queries
        if any(p in text for p in [
            "my ", "mine ", "remember ",
            "what do you know", "tell me about me",
            "what is my", "what are my",
            "what projects", "what project",
            "my goals", "my goal", "my plans", "my plan",
            "my favorite", "my preferences", "my name",
            "about me", "i told you", "i said",
        ]):
            return False

        # Time-sensitive topics -> always search
        if any(p in text for p in [
            "weather", "news", "forecast",
            "latest", "recent", "today", "right now",
            "this week", "this month", "this year",
            "2025", "2026", "2027", "current price",
            "stock", "crypto", "breaking",
        ]):
            return True

        # Factual lookup indicators -> search
        if any(p in text for p in [
            "who is", "who was", "who invented", "who made",
            "what is a ", "what are ", "what does ",
            "where is", "where was", "where can i",
            "when did", "when was", "when is",
            "how much", "how many", "how long", "how far",
            "define ", "meaning of", "explain ",
            "difference between", "compare ",
        ]):
            return True

        return False

    def chat(self, user_message, intent=None, tool_name=None, agent_id=None):

        t_chat = time.time()
        self._last_user_conv_id = None
        self.last_response_metadata = None

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
        # Build Context
        # -------------------------
        t0 = time.time()
        request_context = self.request_context_builder.build(
            user_message,
            session_id=self.session_id,
            agent_id=agent_id,
            query_embedding=user_embedding,
        )
        t_context = time.time() - t0

        conversation_context = request_context.conversation_context

        # Build context before persisting the current turn so the user message
        # appears exactly once in the final prompt.
        user_conversation = self.conversation_repo.create(
            role="user",
            content=user_message,
            session_id=self.session_id,
            embedding=user_embedding,
            intent=intent,
            tool_used=tool_name,
            agent_id=agent_id
        )
        self._last_user_conv_id = user_conversation.id

        # -------------------------
        # Reflexive Web Search
        # -------------------------
        web_results_block = ""
        n_results = 0
        t0 = time.time()

        if self._should_search_web(user_message, agent_id=agent_id):

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

        sections = self._assemble_prompt_sections(
            request_context, user_message, web_results_block
        )
        prompt = self._budget_prompt(sections)

        # -------------------------
        # Generate Response
        # -------------------------
        t0 = time.time()
        explicit_model = self._get_model_for_agent(agent_id)
        use_model = explicit_model or settings.chat_model
        if self.model_router:
            use_model = self.model_router.select(
                user_message,
                task_type="chat",
                explicit_model=explicit_model,
            )
        try:
            response = self.llm.generate_with_model(
                prompt,
                model=use_model
            )
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            return f"I'm having trouble generating a response right now. Please try again. ({e})"
        t_llm = time.time() - t0

        # -------------------------
        # Metrics
        # -------------------------
        metrics = self._model_metrics(prompt, response, t_llm)
        prompt_tokens = metrics["prompt_tokens"]
        response_tokens = metrics["response_tokens"]
        response_time_ms = metrics["response_time_ms"]

        self.last_response_metadata = self.response_finalizer.finalize(
            response,
            user_conversation_id=user_conversation.id,
            session_id=self.session_id,
            agent_id=agent_id,
            model_used=use_model,
            intent=intent,
            tool_used=tool_name,
            response_time_ms=response_time_ms,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
        )

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

    def chat_stream(self, user_message, intent=None, tool_name=None, agent_id=None) -> Iterator[str]:

        t_chat = time.time()
        self._last_user_conv_id = None
        self.last_response_metadata = None

        if len(user_message) > settings.max_input_length:
            yield (
                f"Message too long ({len(user_message)} chars). "
                f"Maximum is {settings.max_input_length} characters."
            )
            return

        user_embedding = None
        if self.embedding_service:
            try:
                user_embedding = (
                    self.embedding_service
                    .generate_embedding(user_message)
                )
            except Exception:
                logger.debug("Failed to generate user embedding", exc_info=True)

        t0 = time.time()
        request_context = self.request_context_builder.build(
            user_message,
            session_id=self.session_id,
            agent_id=agent_id,
            query_embedding=user_embedding,
        )
        t_context = time.time() - t0

        conversation_context = request_context.conversation_context

        user_conversation = self.conversation_repo.create(
            role="user",
            content=user_message,
            session_id=self.session_id,
            embedding=user_embedding,
            intent=intent,
            tool_used=tool_name,
            agent_id=agent_id
        )
        self._last_user_conv_id = user_conversation.id

        web_results_block = ""
        n_results = 0
        t0 = time.time()

        if self._should_search_web(user_message, agent_id=agent_id):
            search_query = user_message

            if conversation_context.strip():
                last_turn = conversation_context.strip().split("\n")[-1]
                search_query = f"{last_turn} {user_message}"

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
                    "Web Search Results:\n" + "\n\n".join(lines)
                )

        t_web = time.time() - t0

        sections = self._assemble_prompt_sections(
            request_context, user_message, web_results_block
        )
        prompt = self._budget_prompt(sections)

        t0 = time.time()
        explicit_model = self._get_model_for_agent(agent_id)
        use_model = explicit_model or settings.chat_model
        if self.model_router:
            use_model = self.model_router.select(
                user_message,
                task_type="chat",
                explicit_model=explicit_model,
            )

        response_chunks = []
        try:
            for chunk in self.llm.generate_stream(prompt, model=use_model):
                response_chunks.append(chunk)
                yield chunk
        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            yield f"I'm having trouble generating a response right now. Please try again. ({e})"
            return

        response = "".join(response_chunks)
        t_llm = time.time() - t0

        metrics = self._model_metrics(prompt, response, t_llm)
        prompt_tokens = metrics["prompt_tokens"]
        response_tokens = metrics["response_tokens"]
        response_time_ms = metrics["response_time_ms"]

        self.last_response_metadata = self.response_finalizer.finalize(
            response,
            user_conversation_id=user_conversation.id,
            session_id=self.session_id,
            agent_id=agent_id,
            model_used=use_model,
            intent=intent,
            tool_used=tool_name,
            response_time_ms=response_time_ms,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
        )

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
