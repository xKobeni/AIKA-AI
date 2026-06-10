import ollama


class EmbeddingService:

    MODEL = "nomic-embed-text"

    def generate_embedding(
        self,
        text: str
    ):

        text = text.strip()

        if not text:
            return None

        response = ollama.embed(
            model=self.MODEL,
            input=text
        )
        
        # print("\n=== EMBEDDING RESPONSE ===")
        # print(response)
        # print("==========================\n")

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