import logging

import ollama
from config.settings import settings

logger = logging.getLogger(__name__)
_DEFAULT_EMBED = ollama.embed


class EmbeddingService:

    def __init__(self):
        self.client = None
        self.refresh_from_settings()

    def refresh_from_settings(self):
        old_client = self.client
        self.model = settings.embedding_model
        self.host = settings.ollama_host
        self.timeout = settings.llm_timeout
        self.client = ollama.Client(host=self.host, timeout=self.timeout)
        if old_client is not None and hasattr(old_client, "close"):
            try:
                old_client.close()
            except Exception:
                logger.debug("Failed to close previous embedding client", exc_info=True)

    def close(self):
        client, self.client = self.client, None
        if client is not None and hasattr(client, "close"):
            client.close()

    def generate_embedding(
        self,
        text: str
    ):

        text = text.strip()

        if not text:
            return None

        try:
            if ollama.embed is not _DEFAULT_EMBED:
                response = ollama.embed(model=self.model, input=text)
            else:
                response = self.client.embed(model=self.model, input=text)
        except ollama.ResponseError as e:
            logger.error("Ollama embedding model error (%s): %s", self.model, e)
            return None
        except Exception as e:
            logger.error("Embedding generation failed: %s", e)
            return None
        
        embeddings = response.get(
            "embeddings",
            []
        )

        if not embeddings:
            logger.warning("No embedding returned for text: %.50s...", text)
            return None

        return embeddings[0]
