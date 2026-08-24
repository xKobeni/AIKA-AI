import logging

import ollama
from config.settings import settings
from database.embedding_compatibility import (
    EmbeddingDimensionError,
    validate_configured_embedding_dimension,
    validate_embedding_vector,
)

logger = logging.getLogger(__name__)
_DEFAULT_EMBED = ollama.embed


class EmbeddingService:

    def __init__(self):
        self.client = None
        self.last_error = None
        self.refresh_from_settings()

    def refresh_from_settings(self):
        if not hasattr(self, "model"):
            self.model = settings.embedding_model
            self.dimension = validate_configured_embedding_dimension(
                settings.embedding_dimension
            )
        elif (
            settings.embedding_model != self.model
            or settings.embedding_dimension != self.dimension
        ):
            logger.warning(
                "Embedding model/dimension changes are startup-only; restart AIKA "
                "after verifying PostgreSQL vector schema compatibility."
            )

        old_client = self.client
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

        self.last_error = None
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

        try:
            return validate_embedding_vector(
                embeddings[0],
                self.dimension,
                name="generated embedding",
            )
        except EmbeddingDimensionError as exc:
            self.last_error = exc
            logger.error(
                "Embedding rejected before persistence/search | "
                "error_type=%s expected=%s actual=%s model=%s",
                type(exc).__name__,
                exc.expected,
                exc.actual,
                self.model,
            )
            return None
