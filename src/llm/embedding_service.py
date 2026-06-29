import ollama
from config.settings import settings


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

        response = ollama.embed(
            model=self.model,
            input=text
        )
        
        embeddings = response.get(
            "embeddings",
            []
        )

        if not embeddings:

            print(
                f"[EmbeddingService] No embedding returned for: {text}"
            )

            return None

        return embeddings[0]