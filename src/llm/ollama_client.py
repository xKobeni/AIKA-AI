import ollama
from config.settings import settings


class OllamaClient:

    def __init__(self):
        self.model = settings.chat_model
        self.host = settings.ollama_host

    def generate(self, prompt):

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]