import ollama


class OllamaClient:

    def generate(self, prompt):

        response = ollama.chat(
            model="llama3.1:8b", 
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        return response["message"]["content"]