MEMORY_PATTERNS = [
    ("project", ["i am building", "i'm building", "i am working on",
                 "i'm working on", "my project", "my startup",
                 "i am creating", "i'm creating", "i am developing",
                 "i'm developing", "i am making", "i'm making"]),
    ("preference", ["i like", "i love", "i prefer", "i enjoy",
                    "i hate", "i dislike", "my favorite",
                    "i am into", "i'm into", "i am interested in",
                    "i'm interested in"]),
    ("goal", ["i want to", "i need to", "i plan to", "my goal",
              "i am trying to", "i'm trying to", "i aim to",
              "i hope to", "my dream", "my target"]),
    ("fact", ["i am", "i'm", "i have", "i've", "i live",
              "my name", "i work", "i study", "i am from",
              "i'm from"]),
    ("skill", ["i know", "i can", "i am good at", "i'm good at",
               "i am experienced in", "i'm experienced in",
               "i am proficient in", "i'm proficient in"]),
]

class MemoryExtractor:

    def __init__(
        self,
        memory_repo,
        embedding_service,
        llm=None,
        memory_validator=None
    ):
        self.memory_repo = memory_repo
        self.embedding_service = embedding_service

    def extract_memory(self, user_message):

        text = f" {user_message.lower().strip()} "

        for category, patterns in MEMORY_PATTERNS:

            for pattern in patterns:

                if pattern in text:

                    idx = text.index(pattern) + len(pattern)
                    content = text[idx:].strip().rstrip(".,!?;:")

                    if len(content) < 3:
                        continue

                    full_content = f"User {category}: {content}"

                    embedding = (
                        self.embedding_service
                        .generate_embedding(full_content)
                    )

                    if embedding is None:
                        return None

                    importance = {
                        "project": 9,
                        "goal": 8,
                        "preference": 6,
                        "fact": 5,
                        "skill": 7
                    }.get(category, 5)

                    print("\n=== MEMORY STORED ===")
                    print("Content:", full_content)
                    print("Category:", category)
                    print("Importance:", importance)
                    print("=====================\n")

                    self.memory_repo.create(
                        memory_type=category,
                        content=full_content,
                        embedding=embedding,
                        category=category,
                        importance=importance
                    )

                    return {
                        "category": category,
                        "content": content
                    }

        return None