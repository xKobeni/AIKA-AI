import json
import re
import logging

logger = logging.getLogger(__name__)


class ToolCallParser:

    def __init__(self, tool_names=None):
        self.tool_names = tool_names or set()

    def parse(self, llm_output):
        text = llm_output.strip()

        json_str = self._extract_json(text)
        if json_str is None:
            logger.debug("No JSON found in LLM output")
            return None

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError:
            fixed = self._fix_common_json_errors(json_str)
            try:
                data = json.loads(fixed)
            except json.JSONDecodeError:
                logger.debug("Failed to parse JSON even after fixes")
                return None

        return self._validate(data)

    def _extract_json(self, text):
        patterns = [
            r"```json\s*\n?(.*?)\n?\s*```",
            r"```\s*\n?(.*?)\n?\s*```",
            r"(\{.*\})",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def _fix_common_json_errors(self, text):
        text = re.sub(r",\s*}", "}", text)
        text = re.sub(r",\s*]", "]", text)
        text = text.replace("'", '"')
        return text

    def _validate(self, data):
        if not isinstance(data, dict):
            return None

        if "tool" not in data:
            return None

        if data["tool"] is None:
            return {"tool": None, "parameters": {}, "response_text": data.get("response", "")}

        tool_name = data["tool"]
        if self.tool_names and tool_name not in self.tool_names:
            logger.warning("LLM requested unknown tool: %s", tool_name)
            return None

        params = data.get("parameters", {})
        if not isinstance(params, dict):
            params = {}

        return {"tool": tool_name, "parameters": params, "response_text": ""}
