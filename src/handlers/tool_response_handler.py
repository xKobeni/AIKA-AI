import logging

from config.settings import settings

logger = logging.getLogger(__name__)


class ToolResponseHandler:

    def __init__(
        self,
        llm
    ):
        self.llm = llm

    def generate_response(
        self,
        user_message,
        tool_name,
        tool_result
    ):

        persona = settings.load_persona()

        prompt = f"""{persona}

User Question:
{user_message}

Tool Used:
{tool_name}

Tool Result:
{tool_result}

RULES:
- Base your answer on the Tool Result — it's your source of truth for facts.
- Present the data naturally with warmth and conversational framing.
- Never invent information. If the result is empty, say so honestly.
- Respond concisely but with genuine emotion and personality."""

        try:
            return self.llm.generate(prompt)
        except Exception as e:
            logger.error("LLM generation failed in tool response: %s", e)
            return f"Here's what the {tool_result} tool returned: {tool_result}"