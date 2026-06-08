class ContextBuilder:

    def build(
        self,
        user_input, 
        memories
    ):

        memory_text = "\n".join(
            [m["content"] for m in memories]
        )

        return f"""
Known Memories:

{memory_text}

User:

{user_input}
"""