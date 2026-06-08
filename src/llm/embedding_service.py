import ollama


class EmbeddingService:

    MODEL = "nomic-embed-text" 

    def generate_embedding(
        self,
        text: str
    ):

        response = ollama.embed(
            model=self.MODEL,
            input=text
        )

        return response["embeddings"][0]