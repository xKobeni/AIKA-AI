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
- Use the Tool Result to answer the user
- Never invent information
- If the result is empty, say so honestly
- Respond naturally"""

        return self.llm.generate(prompt)