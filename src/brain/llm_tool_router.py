import json
import logging
import time

import ollama

from config.settings import settings
from models.actions import Action
from models.tool_request import ToolRequest
from brain.tool_call_parser import ToolCallParser

logger = logging.getLogger(__name__)


class LLMToolRouter:

    SYSTEM_PROMPT = (
        "You are an AI assistant with access to tools. "
        "Analyze the user's request and decide what to do.\n\n"
        "RULES:\n"
        "- If a tool is needed to fulfill the request, use the appropriate tool.\n"
        "- If no tool is needed (general conversation, greeting, opinion, etc), "
        "respond directly with a conversational answer.\n"
        "- Do NOT repeat actions already taken.\n"
        "- If the task is complete, respond directly with your answer.\n"
    )

    LEGACY_SYSTEM_PROMPT = (
        "You are an AI assistant with access to tools. "
        "Analyze the user's request and decide what to do.\n\n"
        "RULES:\n"
        "- If a tool is needed to fulfill the request, respond with ONLY a JSON object:\n"
        '  {"tool": "<tool_name>", "parameters": {"<param>": "<value>"}}\n'
        "- If no tool is needed (general conversation, greeting, opinion, etc), "
        "respond with ONLY:\n"
        '  {"tool": null, "response": "<your conversational response>"}\n'
        "- Do NOT include any text outside the JSON object.\n"
        "- Do NOT use markdown code blocks.\n"
        "- Parameter values must be strings, numbers, or booleans.\n"
        "- Use the tool descriptions below to choose the right tool.\n"
    )

    def __init__(self, tool_manager):
        self.tool_manager = tool_manager
        self.parser = ToolCallParser(
            tool_names=set(tool_manager.tools.keys())
        )
        self.model = settings.chat_model
        self._last_prompt_hash = None
        self._last_result = None
        self.native_tool_calling = getattr(settings, 'native_tool_calling', True)

    def decide_and_route(self, user_message, context_history=None):
        t0 = time.time()

        if self.native_tool_calling:
            return self._decide_native(user_message, context_history, t0)
        return self._decide_legacy(user_message, context_history, t0)

    def _decide_native(self, user_message, context_history, t0):
        native_tools = self.tool_manager.get_native_tool_schemas()
        prompt = self._build_prompt(user_message, context_history)

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ],
                tools=native_tools
            )
        except Exception as e:
            logger.warning("LLM tool routing failed: %s", e)
            return Action.CHAT, None, ""

        content = response["message"].get("content", "").strip()
        tool_calls = response["message"].get("tool_calls", [])

        if tool_calls:
            tc = tool_calls[0]
            func = tc.get("function", {})
            tool_name = func.get("name", "")
            params = dict(func.get("arguments", {}))

            if tool_name not in self.tool_manager.tools:
                logger.warning("Native tool call for unknown tool: %s", tool_name)
                return Action.CHAT, None, content

            tool_request = ToolRequest(tool_name=tool_name, parameters=params)
            logger.debug("Tool call (native): %s (%.2fs)", tool_name, time.time() - t0)
            return Action.USE_TOOL, tool_request, ""

        logger.debug("No tool call, returning CHAT (%.2fs)", time.time() - t0)
        return Action.CHAT, None, content

    def _decide_legacy(self, user_message, context_history, t0):
        prompt = self._build_prompt(user_message, context_history)

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.LEGACY_SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )
            text = response["message"]["content"].strip()
        except Exception as e:
            logger.warning("LLM tool routing failed: %s", e)
            return Action.CHAT, None, ""

        logger.debug("LLM tool router response: %s", text[:200])

        parsed = self.parser.parse(text)

        if parsed is None:
            logger.debug("Parse failed, falling back to CHAT")
            return Action.CHAT, None, ""

        tool_name = parsed["tool"]
        params = parsed["parameters"]
        response_text = parsed.get("response_text", "")

        if tool_name is None:
            return Action.CHAT, None, response_text

        tool_request = ToolRequest(
            tool_name=tool_name,
            parameters=params
        )

        logger.debug(
            "Tool call: %s (%.2fs)",
            tool_name, time.time() - t0
        )

        return Action.USE_TOOL, tool_request, ""

    def _build_prompt(self, user_message, context_history=None):
        if self.native_tool_calling:
            schemas = ""
        else:
            schemas = self.tool_manager.get_schemas_json()

        parts = []
        if schemas:
            parts.append(f"Available tools:\n{schemas}")
            parts.append("")

        if context_history:
            parts.append("Previous actions this session:")
            for entry in context_history[-6:]:
                tool_str = f" -> {entry.get('tool', 'none')}" if entry.get('tool') else ""
                result_preview = str(entry.get('result', ''))[:150]
                parts.append(
                    f"  {entry.get('iteration', '?')}. {entry.get('action', '?')}{tool_str}"
                    f"\n     Result: {result_preview}"
                )
            parts.append("")
            parts.append("Do NOT repeat actions already taken above. If the task is complete, respond directly.")
            parts.append("")

        parts.append(f"User request: {user_message}")

        return "\n".join(parts)
