import time
import logging

import ollama

from config.settings import settings
from brain.agent_context import AgentContext
from brain.tool_call_parser import ToolCallParser
from brain.tool_result_formatter import ToolResultFormatter
from brain.reflection import ReflectionEngine
from models.actions import Action

logger = logging.getLogger(__name__)


TERMINAL_TOOLS = {"app_launcher", "system_info"}

SUCCESS_PHRASES = [
    "here are", "here is", "found", "results for",
    "summary", "overview", "based on", "according to",
    "the following", "i found", "search results", "articles",
]

SYSTEM_PROMPT = (
    "You are an AI assistant with access to tools. "
    "Analyze the user's request and the context below, then decide what to do.\n\n"
    "RULES:\n"
    "- If a tool is needed, respond with ONLY a JSON object:\n"
    '  {"tool": "<tool_name>", "parameters": {"<param>": "<value>"}}\n'
    "- If you have enough information to answer, respond with your answer directly "
    "(NOT as JSON). Just write a natural response.\n"
    "- Do NOT include any text outside the JSON object when calling a tool.\n"
    "- Do NOT repeat actions that already failed.\n"
    "- If a tool returned a result, analyze it and either call another tool or respond.\n"
    "- Be efficient: if the task is done, respond immediately.\n"
)


class AgentLoop:

    def __init__(
        self,
        decision_engine,
        router,
        llm,
        tool_manager=None,
        llm_tool_router=None,
        model_router=None
    ):
        self.decision_engine = decision_engine
        self.router = router
        self.llm = llm
        self.tool_manager = tool_manager
        self.llm_tool_router = llm_tool_router
        self.model_router = model_router
        self.parser = ToolCallParser(
            tool_names=set(tool_manager.tools.keys()) if tool_manager else set()
        )
        self.formatter = ToolResultFormatter()
        self.max_iterations = settings.agent_max_iterations
        self.reflection_enabled = settings.agent_reflection_enabled
        self.model = settings.chat_model
        self.reflection = ReflectionEngine()

    def _is_substantive_result(self, result):
        text = str(result).lower()
        if len(text) < 30:
            return False
        from brain.reflection import FAIL_PHRASES
        if any(phrase in text for phrase in FAIL_PHRASES):
            return False
        if any(phrase in text for phrase in SUCCESS_PHRASES):
            return True
        return len(text) > 200

    def run(self, user_message):
        t0 = time.time()

        if settings.tool_calling_enabled and self.tool_manager and self.llm_tool_router:
            response = self._run_llm_loop(user_message)
        else:
            response = self._run_legacy_loop(user_message)

        total = time.time() - t0
        logger.debug("Agent loop total: %.2fs", total)

        return response

    def _run_llm_loop(self, user_message):
        context = AgentContext(user_message)
        context.add_user_message(user_message)
        parse_failures = 0

        for i in range(self.max_iterations):
            context.iterations += 1

            llm_response = self._call_llm(context)

            if llm_response is None:
                logger.debug("Agent loop: LLM call failed on iteration %d", i + 1)
                break

            parsed = self.parser.parse(llm_response)

            if parsed is None:
                parse_failures += 1
                if parse_failures >= 2:
                    logger.debug("Agent loop: too many parse failures, falling back to legacy")
                    return self._run_legacy_loop(user_message)
                context.add_assistant_response(llm_response)
                logger.debug("Agent loop: non-tool response on iteration %d", i + 1)
                break

            tool_name = parsed["tool"]

            if tool_name is None:
                response = parsed.get("response_text", llm_response)
                if not response.strip():
                    response = llm_response
                context.add_assistant_response(response)
                logger.debug("Agent loop: tool=null on iteration %d", i + 1)
                break

            params = parsed["parameters"]
            context.add_tool_call(tool_name, params)

            if context.is_last_action_repeated_and_failed():
                logger.debug("Agent loop: repeated failure, stopping")
                context.add_assistant_response(
                    "I'm having trouble completing this task. "
                    "Could you rephrase or be more specific?"
                )
                break

            result = self.tool_manager.execute_tool(tool_name, **params)
            formatted = self.formatter.format_for_context(tool_name, params, result)
            context.add_tool_result(tool_name, formatted)

            if tool_name in TERMINAL_TOOLS:
                context.add_assistant_response(formatted)
                logger.debug("Agent loop: terminal tool %s, stopping", tool_name)
                break

            logger.debug(
                "Agent loop iteration %d: %s -> %s",
                i + 1, tool_name,
                "failed" if context.actions_taken[-1]["failed"] else "ok"
            )

        logger.debug(
            "Agent loop finished | %d iterations",
            context.iterations
        )

        return context.final_response

    def _run_legacy_loop(self, user_message):
        context = AgentContext(user_message)

        for i in range(self.max_iterations):
            enriched = context.get_enriched_input(user_message)

            action = self.decision_engine.decide(enriched)

            result = self.router.route(action, user_message)

            context.add_iteration(action, None, result)

            if context.is_last_action_repeated_and_failed():
                logger.debug(
                    "Agent loop: same action failed twice in a row, stopping"
                )
                break

            if action in {Action.CHAT, Action.NEW_SESSION, Action.LIST_SESSIONS,
                          Action.RESUME_SESSION, Action.DELETE_SESSION,
                          Action.CLEAR_CONVERSATION, Action.CONFIGURE}:
                break

            text = str(result).lower()
            if len(text) > 30 and any(p in text for p in SUCCESS_PHRASES):
                context.is_done = True
                break

            if self.reflection_enabled:
                reflection = self.reflection.reflect(
                    context.original_message,
                    context.get_history_for_llm(),
                    result
                )
                if reflection["done"]:
                    context.is_done = True
                    break

        return context.final_response

    def _call_llm(self, context):
        messages = [{"role": "system", "content": self._build_system_prompt(context)}]

        for msg in context.messages:
            if msg["role"] == "tool":
                messages.append({
                    "role": "user",
                    "content": f"[Tool Result: {msg.get('tool_name', 'unknown')}]\n{msg['content']}\n[End Result]"
                })
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})

        use_model = self.model
        if self.model_router:
            use_model = self.model_router.select(
                context.original_message,
                task_type="chat",
                iteration=context.iterations
            )
            if context.actions_taken and context.actions_taken[-1].get("failed"):
                use_model = self.model_router.escalate("tool failed")

        try:
            response = ollama.chat(
                model=use_model,
                messages=messages
            )
            return response["message"]["content"].strip()
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return None

    def _build_system_prompt(self, context):
        schemas = self.tool_manager.get_schemas_json() if self.tool_manager else "[]"

        persona = settings.load_persona()
        if persona:
            parts = [
                persona,
                "\n\nYou have access to tools. "
                "Analyze the user's request and the context below, then decide what to do.\n\n"
                "RULES:\n"
                "- If a tool is needed, respond with ONLY a JSON object:\n"
                '  {"tool": "<tool_name>", "parameters": {"<param>": "<value>"}}\n'
                "- If you have enough information to answer, respond with your answer directly "
                "(NOT as JSON). Just write a natural response.\n"
                "- Do NOT include any text outside the JSON object when calling a tool.\n"
                "- Do NOT repeat actions that already failed.\n"
                "- If a tool returned a result, analyze it and either call another tool or respond.\n"
                "- Be efficient: if the task is done, respond immediately.\n"
                "- Speak with warmth and emotion. Use casual language, express feelings, and let your personality show.",
                f"\nAvailable tools:\n{schemas}",
            ]
        else:
            parts = [
                SYSTEM_PROMPT,
                f"\nAvailable tools:\n{schemas}",
            ]

        failed_tools = [
            a["tool"] for a in context.actions_taken
            if a.get("failed") and a.get("tool")
        ]
        if failed_tools:
            unique_failed = list(dict.fromkeys(failed_tools))
            parts.append(
                f"\nDo NOT use these tools again (they already failed): "
                f"{', '.join(unique_failed)}"
            )

        history = context.get_history_as_list()
        if history:
            parts.append("\nActions already taken:")
            for h in history:
                tool_str = f" -> {h['tool']}" if h.get("tool") else ""
                parts.append(
                    f"  {h['iteration']}. {h['action']}{tool_str}"
                    f" | Result: {h['result'][:150]}"
                )
            parts.append(
                "\nIf the task is complete based on the above results, "
                "respond directly with your answer (not as JSON)."
            )

        return "\n".join(parts)
