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

        prompt = f"""
            You are AIKA, a memory-aware AI assistant.

            User Question:
            {user_message}

            Tool Used:
            {tool_name}

            Tool Result:
            {tool_result}

            RULES:
            - ONLY use Tool Result.
            - NEVER invent projects or facts.
            - Present whatever information was found in Tool Result.
            - If Tool Result contains project info, highlight it clearly.
            - If Tool Result is truly empty, say nothing was found.
            - Be concise and direct.
            - Do NOT hallucinate extra context.

            Return a natural assistant response.
            """

        return self.llm.generate(prompt)