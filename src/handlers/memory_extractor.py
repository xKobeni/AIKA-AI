import json


class MemoryExtractor:

    def __init__(
        self,
        memory_repo,
        embedding_service,
        llm,
        memory_validator
    ):
        self.memory_repo = memory_repo
        self.embedding_service = embedding_service
        self.llm = llm
        self.memory_validator = memory_validator
        
    def extract_memory(self, user_message): 
        prompt = f"""
            You are a memory extraction system for an AI assistant called AIKA.

            Your job is to decide if the user message contains important information worth storing in long-term memory.

            Return ONLY valid JSON.

            Rules:
            - Only store important, meaningful, or persistent information
            - Ignore greetings, small talk, or temporary statements
            - Assign correct category

            Categories:
            - fact
            - project
            - goal
            - preference
            - person
            - skill

            Importance scale:
            1 = trivial
            5 = normal
            10 = critical (core identity or project)

            Return format:

            {{
            "store": true/false,
            "content": "clean memory statement",
            "category": "...",
            "importance": 1-10
            }}

            User message:
            \"{user_message}\"
            """
        
        response = self.llm.generate(prompt)

        # -----------------------------
        # STEP 2: Parse LLM output
        # -----------------------------
        try:
            data = json.loads(response)
        except:
            return None

        # -----------------------------
        # STEP 3: Validate structured data
        # -----------------------------
        validated = self.memory_validator.validate(data)

        if not validated:
            return None

        if not validated.get("store"):
            return None

        # -----------------------------
        # STEP 4: Use cleaned/validated output
        # -----------------------------
        content = validated.get("normalized_content", data["content"])
        category = validated.get("category", data["category"])
        importance = validated.get("importance", data["importance"])

        # -----------------------------
        # STEP 5: Generate embedding
        # -----------------------------
        embedding = self.embedding_service.generate_embedding(content)

        # -----------------------------
        # STEP 6: Store memory
        # -----------------------------
        self.memory_repo.create(
            memory_type=category,
            content=content,
            embedding=embedding,
            category=category
        )

        return validated