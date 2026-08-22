import time
import logging
from typing import Iterator

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
    "When the user asks you to DO something, use a tool. "
    "When the user asks a QUESTION, answer directly.\n\n"

    "## RULES\n"
    "- ALWAYS use a tool when the user asks to open, run, find, read, write, edit, "
    "delete, list, show, search, calculate, or execute something.\n"
    "- Do NOT repeat actions that already failed.\n"
    "- If a tool returned a result, analyze it and either call another tool or respond.\n"
    "- If a request seems harmful, dangerous, or inappropriate, say so clearly.\n"
    "- Do NOT fabricate facts, names, dates, or details you were not given.\n"
    "- If you do not know something, say so honestly instead of guessing.\n"
)

NATIVE_TOOLS_PROMPT = (
    "You are an AI assistant with access to tools. "
    "When the user asks you to DO something, use the appropriate tool. "
    "When the user asks a QUESTION, answer directly.\n\n"
    "## RULES\n"
    "- Use tools when the user asks to open, run, find, read, write, edit, "
    "delete, list, show, search, calculate, or execute something.\n"
    "- Do NOT repeat actions that already failed.\n"
    "- If a tool returned a result, analyze it and either call another tool or respond.\n"
    "- When the task is complete, respond directly with your answer.\n"
    "- If a request seems harmful, dangerous, or inappropriate, say so clearly.\n"
    "- Do NOT fabricate facts, names, dates, or details you were not given.\n"
    "- If you do not know something, say so honestly instead of guessing.\n"
)


class AgentLoop:

    def __init__(
        self,
        decision_engine,
        router,
        llm,
        tool_manager=None,
        llm_tool_router=None,
        model_router=None,
        agent_registry=None,
        orchestrator=None
    ):
        self.decision_engine = decision_engine
        self.router = router
        self.llm = llm
        self.tool_manager = tool_manager
        self.llm_tool_router = llm_tool_router
        self.model_router = model_router
        self.agent_registry = agent_registry
        self._orchestrator = orchestrator
        self.parser = ToolCallParser(
            tool_names=set(tool_manager.tools.keys()) if tool_manager else set()
        )
        self.formatter = ToolResultFormatter()
        self.max_iterations = settings.agent_max_iterations
        self.reflection_enabled = settings.agent_reflection_enabled
        self.model = settings.chat_model
        self.last_model_used = None
        self.reflection = ReflectionEngine(llm=self.llm)
        self.native_tool_calling = getattr(settings, 'native_tool_calling', True)

    def _get_agent_profile(self, agent_id):
        if agent_id and self.agent_registry:
            return self.agent_registry.get(agent_id)
        return None

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

    def run(self, user_message, agent_id=None):
        t0 = time.time()
        self.last_model_used = None

        if settings.tool_calling_enabled and self.tool_manager and self.llm_tool_router:
            response = self._run_llm_loop(user_message, agent_id=agent_id)
        else:
            response = self._run_legacy_loop(user_message, agent_id=agent_id)

        total = time.time() - t0
        logger.debug("Agent loop total: %.2fs", total)

        return response

    def run_stream(self, user_message, agent_id=None) -> Iterator[str]:
        self.last_model_used = None
        if settings.tool_calling_enabled and self.tool_manager and self.llm_tool_router:
            yield from self._run_llm_loop_stream(user_message, agent_id=agent_id)
        else:
            yield self._run_legacy_loop(user_message, agent_id=agent_id)

    def _get_effective_max_iterations(self, agent_id=None):
        profile = self._get_agent_profile(agent_id)
        if profile:
            return profile.max_iterations
        return self.max_iterations

    def _get_effective_model(self, agent_id=None):
        profile = self._get_agent_profile(agent_id)
        if profile and profile.model:
            return profile.model
        return self.model

    def refresh_from_settings(self):
        self.max_iterations = settings.agent_max_iterations
        self.reflection_enabled = settings.agent_reflection_enabled
        self.model = settings.chat_model
        self.native_tool_calling = getattr(settings, 'native_tool_calling', True)
        self.reflection.refresh_from_settings()

    def _check_delegation_intent(self, llm_response, current_agent_id=None):
        import re
        match = re.search(r'\[DELEGATE:\s*(\w+)\]', llm_response, re.IGNORECASE)
        if match:
            target_agent = match.group(1)
            task_match = re.search(r'\[DELEGATE:\s*\w+\]\s*(.*)', llm_response, re.IGNORECASE)
            task = task_match.group(1).strip() if task_match else llm_response
            return target_agent, task
        return None

    def _get_schemas_for_agent(self, agent_id=None):
        if not self.tool_manager:
            return "[]"
        profile = self._get_agent_profile(agent_id)
        if profile and profile.allowed_tools:
            filtered = {
                name: tool for name, tool in self.tool_manager.tools.items()
                if name in profile.allowed_tools
            }
            import json
            schemas = []
            for name, tool in filtered.items():
                schema = tool.get_schema()
                schemas.append(schema)
            return json.dumps(schemas, indent=2)
        return self.tool_manager.get_schemas_json()

    def _get_tool_names_for_agent(self, agent_id=None):
        if not self.tool_manager:
            return set()
        profile = self._get_agent_profile(agent_id)
        if profile and profile.allowed_tools:
            return set(profile.allowed_tools)
        return set(self.tool_manager.tools.keys())

    def _get_native_tools_for_agent(self, agent_id=None):
        if not self.tool_manager or not self.native_tool_calling:
            return []
        profile = self._get_agent_profile(agent_id)
        if profile and profile.allowed_tools:
            return [
                tool.get_native_schema()
                for name, tool in self.tool_manager.tools.items()
                if name in profile.allowed_tools
            ]
        return self.tool_manager.get_native_tool_schemas()

    def _run_llm_loop(self, user_message, agent_id=None):
        context = AgentContext(user_message, agent_id=agent_id)
        context.add_user_message(user_message)
        parse_failures = 0
        max_iter = self._get_effective_max_iterations(agent_id)

        allowed_tools = self._get_tool_names_for_agent(agent_id)
        agent_parser = ToolCallParser(
            tool_names=allowed_tools
        )

        for i in range(max_iter):
            context.iterations += 1

            response_data = self._call_llm(context, agent_id=agent_id)

            if response_data is None:
                logger.debug("Agent loop: LLM call failed on iteration %d", i + 1)
                break

            llm_response = response_data.get("content", "").strip()
            tool_calls = response_data.get("tool_calls", [])

            if not llm_response and not tool_calls:
                logger.warning("Empty response from native tool calling on iteration %d, falling back to legacy", i + 1)
                return self._run_legacy_loop(user_message, agent_id=agent_id)

            delegation = self._check_delegation_intent(llm_response, agent_id)
            if delegation:
                target_agent, task = delegation
                logger.info("LLM delegation detected: %s -> %s", agent_id, target_agent)
                if self._orchestrator is not None:
                    result = self._orchestrator.delegate(agent_id, task, target_agent)
                    context.add_assistant_response(result)
                else:
                    logger.warning("Delegation requested but orchestrator is not available")
                    context.add_assistant_response(llm_response)
                break

            if tool_calls:
                tc = tool_calls[0]
                tool_name = tc["name"]
                params = tc["arguments"]

                if tool_name not in self.tool_manager.tools:
                    logger.warning("Native tool call for unknown tool: %s", tool_name)
                    context.add_assistant_response(llm_response or f"I tried to use tool '{tool_name}' but it doesn't exist.")
                    break

                context.add_tool_call(tool_name, params)

                if context.is_last_action_repeated_and_failed():
                    logger.debug("Agent loop: repeated failure, stopping")
                    context.add_assistant_response(
                        "I'm having trouble completing this task. "
                        "Could you rephrase or be more specific?"
                    )
                    break

                result = self.tool_manager.execute_tool(
                    tool_name, allowed_tool_names=allowed_tools, **params
                )
                formatted = self.formatter.format_for_context(tool_name, params, result)
                context.add_tool_result(tool_name, formatted)

                if tool_name in TERMINAL_TOOLS:
                    context.add_assistant_response(formatted)
                    logger.debug("Agent loop: terminal tool %s, stopping", tool_name)
                    break

                logger.debug(
                    "Agent loop iteration %d (native): %s -> %s",
                    i + 1, tool_name,
                    "failed" if context.actions_taken[-1]["failed"] else "ok"
                )
                continue

            parsed = agent_parser.parse(llm_response)

            if parsed is None:
                parse_failures += 1
                if parse_failures >= 2:
                    logger.debug("Agent loop: too many parse failures, falling back to legacy")
                    return self._run_legacy_loop(user_message, agent_id=agent_id)
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

            result = self.tool_manager.execute_tool(
                tool_name, allowed_tool_names=allowed_tools, **params
            )
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

    def _run_llm_loop_stream(self, user_message, agent_id=None) -> Iterator[str]:
        context = AgentContext(user_message, agent_id=agent_id)
        context.add_user_message(user_message)
        parse_failures = 0
        max_iter = self._get_effective_max_iterations(agent_id)

        allowed_tools = self._get_tool_names_for_agent(agent_id)
        agent_parser = ToolCallParser(
            tool_names=allowed_tools
        )

        for i in range(max_iter):
            context.iterations += 1
            is_last_iteration = (i == max_iter - 1)

            if is_last_iteration:
                yield from self._call_llm_stream(context, agent_id=agent_id)
                break

            response_data = self._call_llm(context, agent_id=agent_id)

            if response_data is None:
                logger.debug("Agent loop: LLM call failed on iteration %d", i + 1)
                break

            llm_response = response_data.get("content", "").strip()
            tool_calls = response_data.get("tool_calls", [])

            if not llm_response and not tool_calls:
                logger.warning("Empty response from native tool calling on iteration %d, falling back to legacy", i + 1)
                yield self._run_legacy_loop(user_message, agent_id=agent_id)
                return

            delegation = self._check_delegation_intent(llm_response, agent_id)
            if delegation:
                target_agent, task = delegation
                logger.info("LLM delegation detected: %s -> %s", agent_id, target_agent)
                if self._orchestrator is not None:
                    result = self._orchestrator.delegate(agent_id, task, target_agent)
                    context.add_assistant_response(result)
                else:
                    logger.warning("Delegation requested but orchestrator is not available")
                    context.add_assistant_response(llm_response)
                break

            if tool_calls:
                tc = tool_calls[0]
                tool_name = tc["name"]
                params = tc["arguments"]

                if tool_name not in self.tool_manager.tools:
                    logger.warning("Native tool call for unknown tool: %s", tool_name)
                    context.add_assistant_response(llm_response or f"I tried to use tool '{tool_name}' but it doesn't exist.")
                    break

                context.add_tool_call(tool_name, params)

                if context.is_last_action_repeated_and_failed():
                    logger.debug("Agent loop: repeated failure, stopping")
                    context.add_assistant_response(
                        "I'm having trouble completing this task. "
                        "Could you rephrase or be more specific?"
                    )
                    break

                result = self.tool_manager.execute_tool(
                    tool_name, allowed_tool_names=allowed_tools, **params
                )
                formatted = self.formatter.format_for_context(tool_name, params, result)
                context.add_tool_result(tool_name, formatted)

                if tool_name in TERMINAL_TOOLS:
                    context.add_assistant_response(formatted)
                    logger.debug("Agent loop: terminal tool %s, stopping", tool_name)
                    break

                logger.debug(
                    "Agent loop iteration %d (native): %s -> %s",
                    i + 1, tool_name,
                    "failed" if context.actions_taken[-1]["failed"] else "ok"
                )
                continue

            parsed = agent_parser.parse(llm_response)

            if parsed is None:
                parse_failures += 1
                if parse_failures >= 2:
                    logger.debug("Agent loop: too many parse failures, falling back to legacy")
                    yield self._run_legacy_loop(user_message, agent_id=agent_id)
                    return
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

            result = self.tool_manager.execute_tool(
                tool_name, allowed_tool_names=allowed_tools, **params
            )
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

        final = context.final_response
        if final:
            yield final

    def _call_llm_stream(self, context, agent_id=None) -> Iterator[str]:
        native_tools = self._get_native_tools_for_agent(agent_id)
        use_native = bool(native_tools)

        system_prompt = self._build_system_prompt(context, agent_id=agent_id, native=use_native)
        messages = [{"role": "system", "content": system_prompt}]

        for msg in context.messages:
            if msg["role"] == "tool":
                messages.append({
                    "role": "tool",
                    "content": f"[Tool Result: {msg.get('tool_name', 'unknown')}]\n{msg['content']}\n[End Result]"
                })
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})

        profile = self._get_agent_profile(agent_id)
        explicit_model = profile.model if profile and profile.model else None
        use_model = explicit_model or self.model
        if self.model_router:
            use_model = self.model_router.select(
                context.original_message,
                task_type="chat",
                iteration=context.iterations,
                explicit_model=explicit_model,
            )
            if (not explicit_model and context.actions_taken
                    and context.actions_taken[-1].get("failed")):
                use_model = self.model_router.escalate("tool failed")

        self.last_model_used = use_model

        try:
            kwargs = {"model": use_model, "messages": messages, "stream": True}
            if use_native:
                kwargs["tools"] = native_tools

            chat_call = (
                self.llm.chat
                if getattr(self.llm, "_uses_configured_client", False) is True
                else ollama.chat
            )
            for chunk in chat_call(**kwargs):
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except Exception as e:
            logger.warning("LLM stream call failed: %s", e)

    def _run_legacy_loop(self, user_message, agent_id=None):
        context = AgentContext(user_message, agent_id=agent_id)
        max_iter = self._get_effective_max_iterations(agent_id)

        for i in range(max_iter):
            enriched = context.get_enriched_input(user_message)

            action = self.decision_engine.decide(enriched)

            result = self.router.route(action, user_message, agent_id=agent_id)

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

    def _call_llm(self, context, agent_id=None):
        native_tools = self._get_native_tools_for_agent(agent_id)
        use_native = bool(native_tools)

        system_prompt = self._build_system_prompt(context, agent_id=agent_id, native=use_native)
        messages = [{"role": "system", "content": system_prompt}]

        for msg in context.messages:
            if msg["role"] == "tool":
                messages.append({
                    "role": "tool",
                    "content": f"[Tool Result: {msg.get('tool_name', 'unknown')}]\n{msg['content']}\n[End Result]"
                })
            else:
                messages.append({"role": msg["role"], "content": msg["content"]})

        profile = self._get_agent_profile(agent_id)
        explicit_model = profile.model if profile and profile.model else None
        use_model = explicit_model or self.model
        if self.model_router:
            use_model = self.model_router.select(
                context.original_message,
                task_type="chat",
                iteration=context.iterations,
                explicit_model=explicit_model,
            )
            if (not explicit_model and context.actions_taken
                    and context.actions_taken[-1].get("failed")):
                use_model = self.model_router.escalate("tool failed")

        self.last_model_used = use_model

        try:
            kwargs = {"model": use_model, "messages": messages}
            if use_native:
                kwargs["tools"] = native_tools

            chat_call = (
                self.llm.chat
                if getattr(self.llm, "_uses_configured_client", False) is True
                else ollama.chat
            )
            response = chat_call(**kwargs)

            content = response["message"].get("content", "").strip()
            tool_calls = []

            raw_tool_calls = response["message"].get("tool_calls")
            if raw_tool_calls:
                for tc in raw_tool_calls:
                    func = tc.get("function", {})
                    tool_calls.append({
                        "name": func.get("name", ""),
                        "arguments": dict(func.get("arguments", {}))
                    })

            return {"content": content, "tool_calls": tool_calls}
        except Exception as e:
            logger.warning("LLM call failed: %s", e)
            return None

    def _load_agent_persona(self, agent_id=None):
        profile = self._get_agent_profile(agent_id)
        if profile and profile.persona_path:
            import os
            if os.path.exists(profile.persona_path):
                try:
                    with open(profile.persona_path, "r", encoding="utf-8") as f:
                        return f.read().strip()
                except Exception as e:
                    logger.warning("Failed to load persona for agent %s: %s", agent_id, e)
        return settings.load_persona()

    def _build_system_prompt(self, context, agent_id=None, native=False):
        if native:
            schemas = ""
            persona = self._load_agent_persona(agent_id)
            if persona:
                parts = [
                    persona,
                    NATIVE_TOOLS_PROMPT,
                ]
            else:
                parts = [
                    NATIVE_TOOLS_PROMPT,
                ]
        else:
            schemas = self._get_schemas_for_agent(agent_id)
            persona = self._load_agent_persona(agent_id)
            if persona:
                parts = [
                    persona,
                    SYSTEM_PROMPT,
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
