import json

STRICT_STORE_CATEGORIES = {
    "project",
    "goal",
    "skill",
    "preference"
}

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
            - If the user is asking a question, do NOT store it
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

        category = validated.get("category", data.get("category", "fact"))
        importance = validated.get("importance", data.get("importance", 5))

        if importance is None:
            importance = 5

        # STRICT FILTER RULE
        if category not in STRICT_STORE_CATEGORIES and importance < 7:
            print("[MemoryExtractor] Rejected low-value memory:", category)
            return None
        
        if category == "project":
            importance = max(importance, 9)
            validated["importance"] = importance

        if category == "goal":
            importance = max(importance, 8)
            validated["importance"] = importance

        # -----------------------------
        # STEP 4: Use cleaned/validated output
        # -----------------------------
        raw_content = data.get("content", "")

        normalized = validated.get("normalized_content")

        if not normalized:
            normalized = raw_content.strip()

        content = normalized

        # -----------------------------
        # STEP 5: Generate embedding
        # -----------------------------
        embedding = (
            self.embedding_service
            .generate_embedding(content)
        )

        if embedding is None:

            print(
                "[MemoryExtractor] Failed to generate embedding"
            )

            return None


        print("\n=== MEMORY STORING ===")
        print("Content:", content)
        print("Category:", category)
        print("Importance:", importance)
        print("======================\n")


        # -----------------------------
        # STEP 6: Store memory
        # -----------------------------
        self.memory_repo.create(
            memory_type=category,
            content=content,
            embedding=embedding,
            category=category,
            importance=importance
        )

        return validated