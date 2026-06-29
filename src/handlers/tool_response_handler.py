from config.settings import settings


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
- Use ONLY the Tool Result to answer. Present data exactly as returned.
- Do NOT interpret, summarize, infer, or add details beyond what is in the Tool Result.
- If the result is a number, list, or structured data, present it verbatim.
- Never invent information. If the result is empty, say so honestly.
- Respond naturally and concisely."""

        return self.llm.generate(prompt)