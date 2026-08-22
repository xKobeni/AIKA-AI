import logging
import threading
from typing import Iterator

import ollama
from config.settings import settings

logger = logging.getLogger(__name__)
_DEFAULT_CHAT = ollama.chat
_DEFAULT_LIST = ollama.list


class OllamaClient:

    _uses_configured_client = True

    def __init__(self):
        self.client = None
        self._metrics = threading.local()
        self.refresh_from_settings()

    @staticmethod
    def _metric_value(response, name):
        if isinstance(response, dict):
            return response.get(name)
        return getattr(response, name, None)

    def _record_metrics(self, response=None):
        metrics = {}
        if response is not None:
            prompt_tokens = self._metric_value(response, "prompt_eval_count")
            response_tokens = self._metric_value(response, "eval_count")
            total_duration = self._metric_value(response, "total_duration")
            if isinstance(prompt_tokens, int):
                metrics["prompt_tokens"] = prompt_tokens
            if isinstance(response_tokens, int):
                metrics["response_tokens"] = response_tokens
            if isinstance(total_duration, (int, float)):
                metrics["response_time_ms"] = int(total_duration / 1_000_000)
        self._metrics.value = metrics

    def get_last_metrics(self):
        return dict(getattr(self._metrics, "value", {}))

    def refresh_from_settings(self):
        old_client = self.client
        self.model = settings.chat_model
        self.host = settings.ollama_host
        self.timeout = settings.llm_timeout
        self.client = ollama.Client(host=self.host, timeout=self.timeout)
        if old_client is not None and hasattr(old_client, "close"):
            try:
                old_client.close()
            except Exception:
                logger.debug("Failed to close previous Ollama client", exc_info=True)

    def _chat(self, **kwargs):
        if ollama.chat is not _DEFAULT_CHAT:
            return ollama.chat(**kwargs)
        return self.client.chat(**kwargs)

    def close(self):
        client, self.client = self.client, None
        if client is not None and hasattr(client, "close"):
            client.close()

    def list_models(self):
        try:
            response = (
                ollama.list()
                if ollama.list is not _DEFAULT_LIST
                else self.client.list()
            )
            return [m["name"] for m in response.get("models", [])]
        except Exception as e:
            logger.warning("Failed to list Ollama models: %s", e)
            return []

    def generate(self, prompt):
        return self.generate_with_model(prompt, model=self.model)

    def chat(self, messages, model=None, tools=None, stream=False):
        kwargs = {
            "model": model or self.model,
            "messages": messages,
            "stream": stream,
        }
        if tools:
            kwargs["tools"] = tools
        self._record_metrics()
        response = self._chat(**kwargs)
        if not stream:
            self._record_metrics(response)
        return response

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
            self._record_metrics()
            response = self._chat(
                model=use_model,
                messages=messages
            )
            self._record_metrics(response)
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
            self._record_metrics()
            for chunk in self._chat(model=use_model, messages=messages, stream=True):
                if any(
                    self._metric_value(chunk, name) is not None
                    for name in ("prompt_eval_count", "eval_count", "total_duration")
                ):
                    self._record_metrics(chunk)
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
            self._record_metrics()
            for chunk in self._chat(model=use_model, messages=messages, stream=True):
                if any(
                    self._metric_value(chunk, name) is not None
                    for name in ("prompt_eval_count", "eval_count", "total_duration")
                ):
                    self._record_metrics(chunk)
                if "message" in chunk and "content" in chunk["message"]:
                    yield chunk["message"]["content"]
        except ollama.ResponseError as e:
            logger.error("Ollama stream error (%s): %s", use_model, e)
            raise
        except Exception as e:
            logger.error("LLM stream failed: %s", e)
            raise
