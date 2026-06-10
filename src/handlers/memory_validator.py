import json

class MemoryValidator:

    def __init__(self, llm, memory_repo=None, embedding_service=None):
        self.llm = llm
        self.memory_repo = memory_repo
        self.embedding_service = embedding_service
        
    def validate(self, memory_data):

        # Pre-check: Semantic deduplication
        content = memory_data.get("content", "")
        if content and self.memory_repo and self.embedding_service:
            embedding = self.embedding_service.generate_embedding(content)
            if embedding:
                existing = self.memory_repo.semantic_search(
                    embedding, limit=3, min_score=0.92
                )
                if existing:
                    return {
                        "store": False,
                        "confidence": 1.0,
                        "reason": "Duplicate - similar memory already exists",
                        "normalized_content": None,
                        "category": None,
                        "importance": None
                    }

        prompt = f"""
            You are a memory validation system for an AI called AIKA.

            Your job is to decide if a memory should be stored.

            RULES:
            - Reject duplicates or near-duplicates
            - Reject unimportant or trivial information
            - Normalize phrasing (clean, short, structured)
            - Ensure memory is useful long-term

            Return ONLY valid JSON.

            Format:
            {{
            "store": true/false,
            "confidence": 0.0-1.0,
            "reason": "...",
            "normalized_content": "...",
            "category": "...",
            "importance": 1-10
            }}

            Memory to evaluate:
            {memory_data}
            """
        
        response = self.llm.generate(prompt)

        try:
            return json.loads(response)
        except:
            return None