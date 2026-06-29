import ollama
from config.settings import settings


class OllamaClient:

    def __init__(self):
        self.model = settings.chat_model
        self.host = settings.ollama_host

    def generate(self, prompt):

        separator = "\nUser:\n"
        if separator in prompt:
            parts = prompt.split(separator, 1)
            messages = [
                {"role": "system", "content": parts[0].strip()},
                {"role": "user", "content": parts[1].strip()}
            ]
        else:
            messages = [
                {"role": "user", "content": prompt}
            ]

        response = ollama.chat(
            model=self.model,
            messages=messages
        )

        return response["message"]["content"]