import time
import logging
from typing import Iterator

import ollama

from config.settings import settings
from brain.agent_context import AgentContext
from brain.prompt_budgeter import PromptBudgeter, PromptSection
from brain.tool_call_parser import ToolCallParser
from brain.tool_result_formatter import ToolResultFormatter
from brain.reflection import ReflectionEngine
from models.actions import Action
from models.tool_request import ToolRequest
from handlers.response_finalizer import STREAM_INTERRUPTION_FALLBACK
from security.redaction import redact_sensitive

logger = logging.getLogger(__name__)


DIRECT_RESPONSE_POLICIES = {"direct_result", "action_confirmation"}

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
        orchestrator=None,
        skill_manager=None,
    ):
        self.decision_engine = decision_engine
        self.router = router
        self.llm = llm
        self.tool_manager = tool_manager
        self.llm_tool_router = llm_tool_router
        self.model_router = model_router
        self.agent_registry = agent_registry
        self.skill_manager = skill_manager
        self._orchestrator = orchestrator
        self.parser = ToolCallParser(
            tool_names=set(tool_manager.tools.keys()) if tool_manager else set()
        )
        self.formatter = ToolResultFormatter()
        self.max_iterations = settings.agent_max_iterations
        self.reflection_enabled = settings.agent_reflection_enabled
        self.model = settings.chat_model
        self.last_model_used = None
        self.last_tool_used = None
        self.last_tools_used = []
        self.last_run_status = "idle"
        self.last_error_type = None
        self.last_iterations = 0
        self.reflection = ReflectionEngine(llm=self.llm)
        self.native_tool_calling = getattr(settings, 'native_tool_calling', True)
        self.prompt_budgeter = PromptBudgeter(settings.max_context_tokens)
        self._last_call_used_tool_fallback = False

    def _reset_run_observability(self):
        self.last_model_used = None
        self.last_tool_used = None
        self.last_tools_used = []
        self.last_run_status = "running"
        self.last_error_type = None
        self.last_iterations = 0

    def _record_tool_execution(self, tool_name, result):
        success = bool(
            result.get("success", False)
            if isinstance(result, dict)
            else result
        )
        self.last_tool_used = tool_name
        self.last_tools_used.append({
            "tool": tool_name,
            "success": success,
        })
        logger.info(
            "Agent tool execution | tool=%s success=%s",
            tool_name,
            success,
        )

    def _complete_run_observability(self, response):
        visible_response = bool(str(response or "").strip())
        if self.last_run_status == "running":
            self.last_run_status = (
                "completed" if visible_response else "empty_response"
            )
        log = (
            logger.info
            if self.last_run_status == "completed"
            else logger.error
        )
        log(
            "Agent run complete | status=%s model=%s tools=%s "
            "iterations=%d response_chars=%d error_type=%s",
            self.last_run_status,
            self.last_model_used,
            [entry["tool"] for entry in self.last_tools_used],
            self.last_iterations,
            len(str(response or "")),
            self.last_error_type,
        )

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

    def run(
        self,
        user_message,
        agent_id=None,
        request_context=None,
        initial_tool_request=None,
    ):
        t0 = time.time()
        self._reset_run_observability()

        if settings.tool_calling_enabled and self.tool_manager and self.llm_tool_router:
            response = self._run_llm_loop(
                user_message,
                agent_id=agent_id,
                request_context=request_context,
                initial_tool_request=initial_tool_request,
            )
        else:
            response = self._run_legacy_loop(user_message, agent_id=agent_id)

        total = time.time() - t0
        logger.debug("Agent loop total: %.2fs", total)
        self._complete_run_observability(response)

        return response

    def run_stream(
        self,
        user_message,
        agent_id=None,
        request_context=None,
        initial_tool_request=None,
    ) -> Iterator[str]:
        self._reset_run_observability()
        response_chunks = []
        try:
            if settings.tool_calling_enabled and self.tool_manager and self.llm_tool_router:
                chunks = self._run_llm_loop_stream(
                    user_message,
                    agent_id=agent_id,
                    request_context=request_context,
                    initial_tool_request=initial_tool_request,
                )
            else:
                chunks = (self._run_legacy_loop(user_message, agent_id=agent_id),)
            for chunk in chunks:
                response_chunks.append(chunk)
                yield chunk
        finally:
            self._complete_run_observability("".join(
                str(chunk) for chunk in response_chunks if chunk is not None
            ))

    def _get_effective_max_iterations(self, agent_id=None):
        profile = self._get_agent_profile(agent_id)
        if profile:
            return profile.max_iterations
        return self.max_iterations

    def _get_response_policy(self, tool_name):
        tool = self.tool_manager.get_tool(tool_name) if self.tool_manager else None
        return getattr(tool, "response_policy", "synthesize")

    def _format_direct_response(self, tool_name, result, formatted):
        if not isinstance(result, dict):
            return str(result)
        if tool_name == "web_search":
            results = result.get("results", [])
            if not results:
                if (
                    result.get("outcome") == "no_results"
                    or result.get("success") is True
                ):
                    return "No matching results were found."
                return "The web-search provider is currently unavailable."
        if not result.get("success", False):
            error = str(result.get("error", "The action failed.")).strip()
            return f"I couldn't complete that action: {error}"
        if tool_name == "app_launcher":
            return str(result.get("message") or "The application was opened.")
        if tool_name == "calculator":
            return f"The answer is {result.get('result', formatted)}."
        if tool_name == "memory_search":
            memories = [
                str(memory).strip()
                for memory in result.get("memories", [])
                if str(memory).strip()
            ]
            if not memories:
                return "I couldn't find any matching memories."
            items = "\n".join(f"- {memory}" for memory in memories)
            return f"Here’s what I found in your memories:\n\n{items}"
        if tool_name == "web_search":
            items = []
            for index, item in enumerate(results[:5], start=1):
                title = str(item.get("title") or "Untitled result").strip()
                url = str(item.get("href") or item.get("url") or "").strip()
                snippet = str(
                    item.get("body") or item.get("snippet") or ""
                ).strip()
                details = [f"{index}. {title}"]
                if snippet:
                    details.append(snippet)
                if url:
                    details.append(url)
                items.append("\n   ".join(details))
            return "Here are the web search results:\n\n" + "\n\n".join(items)
        if tool_name == "folder":
            if result.get("message"):
                return str(result["message"])
            folders = list(result.get("folders", []))
            files = list(result.get("files", []))
            entries = folders + files
            if not entries:
                return f"The folder is empty: {result.get('path', '')}"
            return "Here are the folder contents:\n\n" + "\n".join(
                f"- {entry}" for entry in entries
            )
        if tool_name == "file_write":
            return f"Created {result.get('file_path', 'the file')}."
        return str(result.get("text") or result.get("message") or formatted)

    @staticmethod
    def _web_sources(result):
        if not isinstance(result, dict):
            return []
        sources = []
        for index, item in enumerate(result.get("results", [])[:5], start=1):
            if not isinstance(item, dict):
                continue
            url = str(item.get("href") or item.get("url") or "").strip()
            if not url:
                continue
            title = str(item.get("title") or f"Source {index}").strip()
            sources.append((title, url))
        return sources

    @staticmethod
    def _missing_source_appendix(sources, response):
        missing = [
            (title, url) for title, url in sources
            if url not in str(response or "")
        ]
        if not missing:
            return ""
        return "\n\nSources:\n" + "\n".join(
            f"- {title}: {url}" for title, url in missing
        )

    @staticmethod
    def _web_synthesis_rejection_reason(response, result):
        text = str(response or "").strip()
        if not text:
            return "empty"
        lowered = text.lower()
        if "[tool result" in lowered or "[end result]" in lowered:
            return "tool_wrapper"
        if any(phrase in lowered for phrase in (
            "previously attempted a web search",
            "previously searched the web",
            "earlier web search",
        )):
            return "stale_search_narrative"
        if isinstance(result, dict) and result.get("results"):
            if any(phrase in lowered for phrase in (
                "no search results",
                "no matching results",
                "nothing was found",
                "there are no movies",
                "there aren't any movies",
                "no movies are listed",
            )):
                return "contradicts_nonempty_results"
        return None

    def _synthesize_web_response(
        self, context, result, formatted, agent_id=None, request_context=None
    ):
        fallback = self._format_direct_response(
            "web_search", result, formatted
        )
        if not isinstance(result, dict) or not result.get("results"):
            context.add_assistant_response(fallback)
            return fallback
        response_data = self._call_llm(
            context,
            agent_id=agent_id,
            request_context=request_context,
            allow_tools=False,
        )
        response = (
            str(response_data.get("content", "") or "").strip()
            if response_data is not None
            else ""
        )
        rejection_reason = self._web_synthesis_rejection_reason(
            response, result
        )
        if response and rejection_reason is None:
            response += self._missing_source_appendix(
                self._web_sources(result), response
            )
            self.last_run_status = "completed"
            self.last_error_type = None
        else:
            if rejection_reason not in {None, "empty"}:
                logger.warning(
                    "Rejected web synthesis | reason=%s",
                    rejection_reason,
                )
            response = fallback
            self.last_run_status = "fallback_response"
        context.add_assistant_response(response)
        return response

    def _synthesize_web_response_stream(
        self, context, result, formatted, agent_id=None, request_context=None
    ):
        fallback = self._format_direct_response(
            "web_search", result, formatted
        )
        if not isinstance(result, dict) or not result.get("results"):
            context.add_assistant_response(fallback)
            yield fallback
            return
        response = "".join(self._call_llm_stream(
            context,
            agent_id=agent_id,
            request_context=request_context,
            allow_tools=False,
            retry_empty=False,
            empty_fallback=fallback,
            required_sources=self._web_sources(result),
        ))
        rejection_reason = self._web_synthesis_rejection_reason(
            response, result
        )
        if rejection_reason not in {None, "empty"}:
            logger.warning(
                "Rejected streamed web synthesis | reason=%s",
                rejection_reason,
            )
            response = fallback
            self.last_run_status = "fallback_response"
            self.last_error_type = None
        elif not response.strip():
            response = fallback
            self.last_run_status = "fallback_response"
        context.add_assistant_response(response)
        yield response

    def _fallback_response(self, context):
        if context.actions_taken:
            last_tool_succeeded = (
                bool(self.last_tools_used)
                and self.last_tools_used[-1].get("success") is True
            )
            if (
                not last_tool_succeeded
                and context.actions_taken[-1].get("failed")
            ):
                return (
                    "I couldn't complete the requested action. "
                    "Please check the tool result or try again."
                )
            return (
                "I completed the tool action, but I couldn't generate the "
                "final response. Please try again."
            )
        return "I couldn't generate a response just now. Please try again."

    def _execute_tool_request(self, context, request, allowed_tools, agent_id=None):
        tool_name = request.tool_name
        parameters = dict(request.parameters or {})
        context.add_tool_call(tool_name, parameters)
        result = self.tool_manager.execute_tool(
            tool_name,
            allowed_tool_names=allowed_tools,
            agent_id=agent_id,
            **parameters,
        )
        self._record_tool_execution(tool_name, result)
        formatted = self.formatter.format_for_context(
            tool_name, parameters, result
        )
        context.add_tool_result(tool_name, formatted)
        return tool_name, result, formatted

    def _apply_response_policy(self, context, tool_name, result, formatted):
        policy = self._get_response_policy(tool_name)
        if policy not in DIRECT_RESPONSE_POLICIES:
            return False
        context.add_assistant_response(
            self._format_direct_response(tool_name, result, formatted)
        )
        logger.debug(
            "Agent loop: %s response policy for %s",
            policy,
            tool_name,
        )
        return True

    def _synthesize_response(self, context, agent_id=None, request_context=None):
        response_data = self._call_llm(
            context,
            agent_id=agent_id,
            request_context=request_context,
            allow_tools=False,
        )
        response = ""
        if response_data is not None:
            response = str(response_data.get("content", "") or "").strip()
        if not response:
            response = self._fallback_response(context)
            if self.last_run_status == "running":
                self.last_run_status = "fallback_response"
        context.add_assistant_response(response)
        return response

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
        self.prompt_budgeter.set_limit(settings.max_context_tokens)
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

    def _run_llm_loop(
        self,
        user_message,
        agent_id=None,
        request_context=None,
        initial_tool_request=None,
    ):
        context = AgentContext(user_message, agent_id=agent_id)
        context.add_user_message(user_message)
        parse_failures = 0
        max_iter = self._get_effective_max_iterations(agent_id)

        allowed_tools = self._get_tool_names_for_agent(agent_id)
        agent_parser = ToolCallParser(
            tool_names=allowed_tools
        )

        if initial_tool_request is not None:
            context.iterations += 1
            self.last_iterations = context.iterations
            tool_name, result, formatted = self._execute_tool_request(
                context, initial_tool_request, allowed_tools, agent_id=agent_id
            )
            if self._apply_response_policy(
                context, tool_name, result, formatted
            ):
                return context.final_response
            if tool_name == "web_search":
                return self._synthesize_web_response(
                    context,
                    result,
                    formatted,
                    agent_id=agent_id,
                    request_context=request_context,
                )

        for i in range(max_iter):
            context.iterations += 1
            self.last_iterations = context.iterations

            response_data = self._call_llm(
                context,
                agent_id=agent_id,
                request_context=request_context,
            )
            used_tool_fallback = self._last_call_used_tool_fallback

            if response_data is None:
                logger.debug("Agent loop: LLM call failed on iteration %d", i + 1)
                break

            llm_response = response_data.get("content", "").strip()
            tool_calls = response_data.get("tool_calls", [])

            if used_tool_fallback and not tool_calls:
                return self._synthesize_response(
                    context,
                    agent_id=agent_id,
                    request_context=request_context,
                )

            if not llm_response and not tool_calls:
                logger.warning(
                    "Empty native response on iteration %d; forcing a visible response",
                    i + 1,
                )
                if context.actions_taken:
                    return self._synthesize_response(
                        context,
                        agent_id=agent_id,
                        request_context=request_context,
                    )
                legacy = self._run_legacy_loop(
                    user_message, agent_id=agent_id
                )
                return legacy or self._fallback_response(context)

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

                _, result, formatted = self._execute_tool_request(
                    context,
                    ToolRequest(tool_name, params),
                    allowed_tools,
                    agent_id=agent_id,
                )
                self.last_iterations = context.iterations

                if context.is_last_action_repeated_and_failed():
                    logger.debug("Agent loop: repeated failure, stopping")
                    context.add_assistant_response(
                        "I'm having trouble completing this task. "
                        "Could you rephrase or be more specific?"
                    )
                    break

                if self._apply_response_policy(
                    context, tool_name, result, formatted
                ):
                    break
                if tool_name == "web_search":
                    return self._synthesize_web_response(
                        context,
                        result,
                        formatted,
                        agent_id=agent_id,
                        request_context=request_context,
                    )

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
            _, result, formatted = self._execute_tool_request(
                context,
                ToolRequest(tool_name, params),
                allowed_tools,
                agent_id=agent_id,
            )
            self.last_iterations = context.iterations

            if context.is_last_action_repeated_and_failed():
                logger.debug("Agent loop: repeated failure, stopping")
                context.add_assistant_response(
                    "I'm having trouble completing this task. "
                    "Could you rephrase or be more specific?"
                )
                break

            if self._apply_response_policy(
                context, tool_name, result, formatted
            ):
                break
            if tool_name == "web_search":
                return self._synthesize_web_response(
                    context,
                    result,
                    formatted,
                    agent_id=agent_id,
                    request_context=request_context,
                )

            logger.debug(
                "Agent loop iteration %d: %s -> %s",
                i + 1, tool_name,
                "failed" if context.actions_taken[-1]["failed"] else "ok"
            )

        logger.debug(
            "Agent loop finished | %d iterations",
            context.iterations
        )

        if not context.final_response:
            if context.actions_taken:
                self._synthesize_response(
                    context,
                    agent_id=agent_id,
                    request_context=request_context,
                )
            else:
                context.add_assistant_response(self._fallback_response(context))
        return context.final_response

    def _run_llm_loop_stream(
        self,
        user_message,
        agent_id=None,
        request_context=None,
        initial_tool_request=None,
    ) -> Iterator[str]:
        context = AgentContext(user_message, agent_id=agent_id)
        context.add_user_message(user_message)
        parse_failures = 0
        max_iter = self._get_effective_max_iterations(agent_id)

        allowed_tools = self._get_tool_names_for_agent(agent_id)
        agent_parser = ToolCallParser(
            tool_names=allowed_tools
        )

        if initial_tool_request is not None:
            context.iterations += 1
            self.last_iterations = context.iterations
            tool_name, result, formatted = self._execute_tool_request(
                context, initial_tool_request, allowed_tools, agent_id=agent_id
            )
            if self._apply_response_policy(
                context, tool_name, result, formatted
            ):
                yield context.final_response
                return
            if tool_name == "web_search":
                yield from self._synthesize_web_response_stream(
                    context,
                    result,
                    formatted,
                    agent_id=agent_id,
                    request_context=request_context,
                )
                return

        for i in range(max_iter):
            context.iterations += 1
            self.last_iterations = context.iterations
            is_last_iteration = (i == max_iter - 1)

            if is_last_iteration:
                yield from self._call_llm_stream(
                    context,
                    agent_id=agent_id,
                    request_context=request_context,
                    allow_tools=False,
                )
                return

            response_data = self._call_llm(
                context,
                agent_id=agent_id,
                request_context=request_context,
            )
            used_tool_fallback = self._last_call_used_tool_fallback

            if response_data is None:
                logger.debug("Agent loop: LLM call failed on iteration %d", i + 1)
                if context.actions_taken:
                    yield from self._call_llm_stream(
                        context,
                        agent_id=agent_id,
                        request_context=request_context,
                        allow_tools=False,
                    )
                    return
                else:
                    yield self._fallback_response(context)
                    return

            llm_response = response_data.get("content", "").strip()
            tool_calls = response_data.get("tool_calls", [])

            if used_tool_fallback and not tool_calls:
                yield from self._call_llm_stream(
                    context,
                    agent_id=agent_id,
                    request_context=request_context,
                    allow_tools=False,
                )
                return

            if not llm_response and not tool_calls:
                logger.warning(
                    "Empty native response on iteration %d; forcing final synthesis",
                    i + 1,
                )
                yield from self._call_llm_stream(
                    context,
                    agent_id=agent_id,
                    request_context=request_context,
                    allow_tools=False,
                )
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

                _, result, formatted = self._execute_tool_request(
                    context,
                    ToolRequest(tool_name, params),
                    allowed_tools,
                    agent_id=agent_id,
                )
                self.last_iterations = context.iterations

                if context.is_last_action_repeated_and_failed():
                    logger.debug("Agent loop: repeated failure, stopping")
                    context.add_assistant_response(
                        "I'm having trouble completing this task. "
                        "Could you rephrase or be more specific?"
                    )
                    break

                if self._apply_response_policy(
                    context, tool_name, result, formatted
                ):
                    break
                if tool_name == "web_search":
                    yield from self._synthesize_web_response_stream(
                        context,
                        result,
                        formatted,
                        agent_id=agent_id,
                        request_context=request_context,
                    )
                    return

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
            _, result, formatted = self._execute_tool_request(
                context,
                ToolRequest(tool_name, params),
                allowed_tools,
                agent_id=agent_id,
            )
            self.last_iterations = context.iterations

            if context.is_last_action_repeated_and_failed():
                logger.debug("Agent loop: repeated failure, stopping")
                context.add_assistant_response(
                    "I'm having trouble completing this task. "
                    "Could you rephrase or be more specific?"
                )
                break

            if self._apply_response_policy(
                context, tool_name, result, formatted
            ):
                break
            if tool_name == "web_search":
                yield from self._synthesize_web_response_stream(
                    context,
                    result,
                    formatted,
                    agent_id=agent_id,
                    request_context=request_context,
                )
                return

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
        else:
            yield self._fallback_response(context)

    def _prepare_llm_request(
        self,
        context,
        *,
        agent_id=None,
        request_context=None,
        allow_tools=True,
        model=None,
    ):
        """Budget system context, messages, and tool schemas as one payload."""
        self.prompt_budgeter.set_limit(settings.max_context_tokens)
        supports_tools = self._model_supports_tools(model)
        tools_allowed = allow_tools and supports_tools is not False
        native_tools = (
            self._get_native_tools_for_agent(agent_id)
            if tools_allowed
            else []
        )
        use_native = bool(native_tools)
        system_sections = self._build_system_prompt_sections(
            context,
            agent_id=agent_id,
            native=use_native,
            request_context=request_context,
            include_tools=tools_allowed,
        )
        context_messages = [
            {
                "role": message.get("role", "user"),
                "content": str(message.get("content", "") or ""),
            }
            for message in context.messages
        ]
        messages, budgeted_tools = self.prompt_budgeter.budget_agent_request(
            system_sections,
            context_messages,
            native_tools,
            current_user_text=context.original_message,
        )

        # If no native schema can fit, rebuild as a bounded legacy prompt rather
        # than claiming native tool access without sending a usable definition.
        if use_native and not budgeted_tools:
            system_sections = self._build_system_prompt_sections(
                context,
                agent_id=agent_id,
                native=False,
                request_context=request_context,
                include_tools=tools_allowed,
            )
            messages, budgeted_tools = self.prompt_budgeter.budget_agent_request(
                system_sections,
                context_messages,
                [],
                current_user_text=context.original_message,
            )

        if len(budgeted_tools) < len(native_tools):
            logger.warning(
                "Prompt budget limited native tool schemas | included=%d total=%d",
                len(budgeted_tools),
                len(native_tools),
            )
        return messages, budgeted_tools

    def _model_supports_tools(self, model):
        checker = getattr(self.llm, "supports_tools", None)
        if not callable(checker) or not model:
            return None
        try:
            return checker(model)
        except Exception as exc:
            logger.warning(
                "Model capability check failed | model=%s error_type=%s",
                model,
                type(exc).__name__,
            )
            return None

    def _preferred_model(self, context, agent_id=None):
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
            if (
                not explicit_model
                and context.actions_taken
                and context.actions_taken[-1].get("failed")
            ):
                use_model = self.model_router.escalate("tool failed")
        return use_model

    def _model_for_call(self, preferred_model, *, allow_tools):
        self._last_call_used_tool_fallback = False
        if not allow_tools or self._model_supports_tools(preferred_model) is not False:
            return preferred_model

        candidates = []
        if self.model_router is not None:
            candidates.append(getattr(self.model_router, "fast", None))
        candidates.append(self.model)
        for candidate in candidates:
            candidate = str(candidate or "").strip()
            if not candidate or candidate == preferred_model:
                continue
            if self._model_supports_tools(candidate) is False:
                continue
            self._last_call_used_tool_fallback = True
            logger.info(
                "Using tool-capable model for action selection | preferred=%s "
                "selected=%s",
                preferred_model,
                candidate,
            )
            return candidate

        logger.warning(
            "Selected model does not support tools and no compatible fallback "
            "was found | model=%s",
            preferred_model,
        )
        return preferred_model

    @staticmethod
    def _safe_error_detail(exc):
        detail = str(redact_sensitive(str(exc) or type(exc).__name__))
        return detail.replace("\r", " ").replace("\n", " ")[:300]

    def _call_llm_stream(
        self,
        context,
        agent_id=None,
        request_context=None,
        allow_tools=True,
        retry_empty=True,
        empty_fallback=None,
        required_sources=None,
    ) -> Iterator[str]:
        preferred_model = self._preferred_model(context, agent_id=agent_id)
        use_model = self._model_for_call(
            preferred_model,
            allow_tools=allow_tools,
        )
        messages, native_tools = self._prepare_llm_request(
            context,
            agent_id=agent_id,
            request_context=request_context,
            allow_tools=allow_tools,
            model=use_model,
        )
        use_native = bool(native_tools)

        self.last_model_used = use_model

        yielded_content = False
        emitted_content = []
        stream_interrupted = False
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
                    content = str(chunk["message"]["content"] or "")
                    if content:
                        yielded_content = True
                        emitted_content.append(content)
                        yield content
        except Exception as e:
            stream_interrupted = True
            self.last_run_status = "llm_error"
            self.last_error_type = type(e).__name__
            logger.warning(
                "LLM stream call failed | error_type=%s detail=%s",
                self.last_error_type,
                self._safe_error_detail(e),
            )

        if yielded_content:
            if stream_interrupted:
                suffix = "\n\n" + STREAM_INTERRUPTION_FALLBACK
                suffix += self._missing_source_appendix(
                    required_sources or [], "".join(emitted_content) + suffix
                )
                yield suffix
                return
            appendix = self._missing_source_appendix(
                required_sources or [], "".join(emitted_content)
            )
            if appendix:
                yield appendix
            self.last_run_status = "completed"
            self.last_error_type = None
            return

        if not yielded_content:
            if not retry_empty:
                fallback = str(empty_fallback or self._fallback_response(context))
                fallback += self._missing_source_appendix(
                    required_sources or [], fallback
                )
                self.last_run_status = "fallback_response"
                yield fallback
                return
            retry = self._call_llm(
                context,
                agent_id=agent_id,
                request_context=request_context,
                allow_tools=False,
            )
            retry_text = (
                str(retry.get("content", "") or "").strip()
                if retry is not None
                else ""
            )
            if retry_text:
                self.last_run_status = "completed"
                self.last_error_type = None
                yield retry_text
            else:
                if self.last_run_status == "running":
                    self.last_run_status = "fallback_response"
                yield self._fallback_response(context)

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

    def _call_llm(
        self,
        context,
        agent_id=None,
        request_context=None,
        allow_tools=True,
    ):
        preferred_model = self._preferred_model(context, agent_id=agent_id)
        use_model = self._model_for_call(
            preferred_model,
            allow_tools=allow_tools,
        )
        messages, native_tools = self._prepare_llm_request(
            context,
            agent_id=agent_id,
            request_context=request_context,
            allow_tools=allow_tools,
            model=use_model,
        )
        use_native = bool(native_tools)

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
        except Exception as exc:
            self.last_run_status = "llm_error"
            self.last_error_type = type(exc).__name__
            logger.warning(
                "LLM call failed | error_type=%s detail=%s",
                self.last_error_type,
                self._safe_error_detail(exc),
            )
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

    def _build_system_prompt(
        self,
        context,
        agent_id=None,
        native=False,
        request_context=None,
        include_tools=True,
    ):
        return "\n".join(
            section.text
            for section in self._build_system_prompt_sections(
                context,
                agent_id=agent_id,
                native=native,
                request_context=request_context,
                include_tools=include_tools,
            )
        )

    def _build_system_prompt_sections(
        self,
        context,
        agent_id=None,
        native=False,
        request_context=None,
        include_tools=True,
    ):
        parts = self._build_system_prompt_parts(
            context,
            agent_id=agent_id,
            native=native,
            request_context=request_context,
            include_tools=include_tools,
        )
        sections = []
        for index, part in enumerate(parts):
            upper = part.upper()
            is_base_rules = part in {SYSTEM_PROMPT, NATIVE_TOOLS_PROMPT}
            is_grounding = (
                "IDENTITY AND GROUNDING RULES" in upper
                or "WEB SEARCH GROUNDING RULES" in upper
            )
            is_failed_tool_rule = "DO NOT USE THESE TOOLS AGAIN" in upper
            is_completion_rule = "IF THE TASK IS COMPLETE" in upper
            is_recent = "=== RECENT CONVERSATION ===" in upper
            is_tool_definition = "AVAILABLE TOOLS:" in upper
            is_active_skill = "=== ACTIVE SKILL:" in upper

            priority = 95 if (is_base_rules or is_grounding) else 90 if (
                is_failed_tool_rule or is_completion_rule
            ) else 85 if is_active_skill else 80 if (
                is_tool_definition or "TOOLS AVAILABLE TO THE CURRENT AGENT" in upper
            ) else 70 if is_recent else 65 if (
                "CURRENT TIME:" in upper or "ACTIONS ALREADY TAKEN" in upper
            ) else 55
            if part.startswith("  ") and " | Result:" in part:
                priority = 65 + index

            sections.append(PromptSection(
                key=f"system:{index}",
                text=part,
                priority=priority,
                required=(
                    is_base_rules or is_grounding
                    or is_failed_tool_rule or is_completion_rule
                    or is_active_skill
                ),
                keep="end" if is_recent else "start",
            ))
        return sections

    def _build_system_prompt_parts(
        self,
        context,
        agent_id=None,
        native=False,
        request_context=None,
        include_tools=True,
    ):
        persona = (
            request_context.persona
            if request_context is not None
            else self._load_agent_persona(agent_id)
        )
        if native:
            schemas = ""
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
            schemas = self._get_schemas_for_agent(agent_id) if include_tools else ""
            if persona:
                parts = [
                    persona,
                    SYSTEM_PROMPT,
                ]
            else:
                parts = [
                    SYSTEM_PROMPT,
                ]
            if schemas:
                parts.append(f"\nAvailable tools:\n{schemas}")

        if request_context is not None:
            parts.extend(
                request_context.prompt_sections(include_persona=False)
            )
            if self.skill_manager is not None:
                skill_prompt = self.skill_manager.prompt_for(
                    session_id=request_context.session_id,
                    agent_id=agent_id or request_context.agent_id,
                )
                if skill_prompt:
                    parts.append(skill_prompt)

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

        if any(
            action.get("tool") == "web_search"
            for action in context.actions_taken
        ):
            parts.append(
                "\nWEB SEARCH GROUNDING RULES:\n"
                "- Answer the user's question using only the web_search result.\n"
                "- Do not invent titles, rankings, dates, descriptions, or URLs.\n"
                "- This search ran for the current turn; do not describe it as a "
                "previous or earlier search.\n"
                "- Never echo [Tool Result] or [End Result] wrapper text.\n"
                "- Nonempty results must not be described as no results.\n"
                "- If the search failed, explain that failure instead of guessing.\n"
                "- Include useful result links in the answer.\n"
                "- Do not request or call another tool."
            )

        return parts
