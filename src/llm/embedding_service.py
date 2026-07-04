import logging

import ollama
from config.settings import settings

logger = logging.getLogger(__name__)


class EmbeddingService:

    def __init__(self):
        self.model = settings.embedding_model

    def generate_embedding(
        self,
        text: str
    ):

        text = text.strip()

        if not text:
            return None

        try:
            response = ollama.embed(
                model=self.model,
                input=text
            )
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