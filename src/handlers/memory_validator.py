import json

class MemoryValidator:

    def __init__(self, llm):
        self.llm = llm
        
    def validate(self, memory_data):

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