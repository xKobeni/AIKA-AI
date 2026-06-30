import logging

from config.settings import settings

logger = logging.getLogger(__name__)

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
    ("person", ["my friend", "my wife", "my husband", "my partner",
                "my boss", "my colleague", "my teacher",
                "i work with", "i met", "my family",
                "my mom", "my dad", "my brother", "my sister"]),
    ("decision", ["i decided", "i chose", "we agreed", "i went with",
                  "i chose to", "i decided to", "i settled on",
                  "we decided", "the plan is", "the decision is"]),
    ("outcome", ["it worked", "it failed", "the result was",
                 "i learned that", "it turned out", "what happened",
                 "the outcome", "in the end", "as a result",
                 "it succeeded"]),
]

IMPORTANCE_MAP = {
    "project": 9,
    "goal": 8,
    "decision": 8,
    "skill": 7,
    "person": 7,
    "outcome": 7,
    "preference": 6,
    "fact": 5,
}

CATEGORY_WEIGHTS = {
    "project": 0.3,
    "goal": 0.2,
    "skill": 0.1,
    "preference": 0.05,
    "person": 0.1,
    "decision": 0.15,
    "outcome": 0.1,
    "fact": 0.0,
}


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
        self.log_level = settings.log_level
        self.dedup_threshold = settings.memory_dedup_threshold
        self.max_per_message = settings.memory_extraction_max_per_message

    def _is_duplicate(self, content, category):
        try:
            embedding = self.embedding_service.generate_embedding(content)
            if embedding is None:
                return False

            existing = self.memory_repo.semantic_search(
                embedding, limit=1
            )

            if existing and len(existing) > 0:
                score = getattr(existing[0], '_score', 0)
                if score >= self.dedup_threshold:
                    logger.debug(
                        "Memory dedup: '%s' too similar to existing (score=%.2f)",
                        content[:50], score
                    )
                    return True

        except Exception as e:
            logger.debug("Dedup check failed: %s", e)

        return False

    def extract_memory(self, user_message, source_conversation_id=None):

        text = f" {user_message.lower().strip()} "
        extracted = []

        for category, patterns in MEMORY_PATTERNS:

            if len(extracted) >= self.max_per_message:
                break

            for pattern in patterns:

                if pattern in text:

                    idx = text.index(pattern) + len(pattern)
                    content = text[idx:].strip().rstrip(".,!?;:")

                    if len(content) < 3:
                        continue

                    if self._is_duplicate(content, category):
                        continue

                    full_content = f"User {category}: {content}"

                    embedding = (
                        self.embedding_service
                        .generate_embedding(full_content)
                    )

                    if embedding is None:
                        continue

                    importance = IMPORTANCE_MAP.get(category, 5)

                    logger.info(
                        "Memory stored | content=%s | category=%s | importance=%d",
                        full_content, category, importance
                    )

                    self.memory_repo.create(
                        memory_type=category,
                        content=full_content,
                        embedding=embedding,
                        category=category,
                        importance=importance,
                        source_conversation_id=source_conversation_id
                    )

                    extracted.append({
                        "category": category,
                        "content": content
                    })

                    break

        return extracted[0] if len(extracted) == 1 else extracted or None