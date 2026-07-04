import logging
from typing import Iterator

import ollama
from config.settings import settings

logger = logging.getLogger(__name__)


class OllamaClient:

    def __init__(self):
        self.model = settings.chat_model
        self.host = settings.ollama_host

    def list_models(self):
        try:
            response = ollama.list()
            return [m["name"] for m in response.get("models", [])]
        except Exception as e:
            logger.warning("Failed to list Ollama models: %s", e)
            return []

    def generate(self, prompt):
        return self.generate_with_model(prompt, model=self.model)

    def generate_with_model(self, prompt, model=None):
        use_model = model or self.model

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

        try:
            response = ollama.chat(
                model=use_model,
                messages=messages
            )
            return response["message"]["content"]
        except ollama.ResponseError as e:
            logger.error("Ollama model error (%s): %s", use_model, e)
            raise
        except Exception as e:
            logger.error("LLM generation failed: %s", e)
            raise

    def generate_stream(self, prompt, model=None) -> Iterator[str]:
        use_model = model or self.model

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

        try:
            for chunk in ollama.chat(model=use_model, messages=messages, stream=True):
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except ollama.ResponseError as e:
            logger.error("Ollama stream error (%s): %s", use_model, e)
            raise
        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            raise

    def chat_stream(self, messages, model=None) -> Iterator[str]:
        use_model = model or self.model
        try:
            for chunk in ollama.chat(model=use_model, messages=messages, stream=True):
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except ollama.ResponseError as e:
            logger.error("Ollama stream error (%s): %s", use_model, e)
            raise
        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            raise