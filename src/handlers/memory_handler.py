from config.settings import settings

class MemoryHandler:

    def __init__(
        self,
        memory_repo,
        embedding_service,
        retrieval_service=None
    ):

        self.memory_repo = memory_repo
        self.embedding_service = embedding_service
        self.retrieval_service = retrieval_service
        self.retrieval_limit = settings.memory_retrieval_limit

    def store_memory(
        self,
        user_message
    ):

        raw = user_message[9:]

        if ":" in raw:

            memory_type, content = raw.split(
                ":",
                1
            )

            memory_type = memory_type.strip()
            content = content.strip()

            type_importance = {
                "project": 9, "goal": 8,
                "skill": 6, "preference": 6,
                "person": 5, "fact": 5
            }
            importance = type_importance.get(memory_type, 5)

            embedding = self.embedding_service.generate_embedding(content)

            self.memory_repo.create(
                memory_type,
                content,
                embedding,
                category=memory_type,
                importance=importance
            )

            return f"Stored {memory_type} memory."

        content = raw.strip()
        embedding = self.embedding_service.generate_embedding(content)

        self.memory_repo.create(
            "fact",
            content,
            embedding,
            importance=5
        )

        return "Memory stored."

    def list_memories(self):

        
        memories = self.memory_repo.get_all()

        if not memories:
            return "No memories stored."

        lines = []

        for memory in memories:

            lines.append(
                f"[{memory.id}] "
                f"({memory.type}) "
                f"Importance:{memory.importance} "
                f"Uses:{memory.access_count} "
                f"{memory.content}"
            )

        return "\n".join(lines)

    def search_memory(
        self,
        query
    ):

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                query,
                limit=self.retrieval_limit
            )

            if isinstance(result, str):
                return result

            if not result:
                return "No memories found."

            return "\n".join(
                m.content for m in result
            )

        query_embedding = (
            self.embedding_service
            .generate_embedding(query)
        )

        if not query_embedding:
            return "No memories found."

        results = self.memory_repo.semantic_search(
            query_embedding
        )

        if not results:
            return "No memories found."

        return "\n".join(
            [
                m.content
                for m in results
            ]
        )

    def delete_memory(
        self,
        memory_id
    ):

        self.memory_repo.delete(
            memory_id
        )

        return (
            f"Deleted memory "
            f"{memory_id}"
        )
        
    def semantic_search_memory(
        self,
        query
    ):

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                query,
                limit=self.retrieval_limit
            )

            if isinstance(result, str):
                return []

            return result

        query_embedding = (
            self.embedding_service
            .generate_embedding(query)
        )

        memories = (
            self.memory_repo
            .semantic_search(
                query_embedding
            )
        )

        return memories