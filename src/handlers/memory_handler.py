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

    def refresh_from_settings(self):
        self.retrieval_limit = settings.memory_retrieval_limit

    def store_memory(
        self,
        user_message,
        agent_id=None
    ):

        raw = user_message.split(" ", 1)[1] if " " in user_message else ""

        if ":" in raw:

            memory_type, content = raw.split(
                ":",
                1
            )

            memory_type = memory_type.strip()
            content = content.strip()

            if not content:
                return "No memory content provided."

            type_importance = {
                "project": 9, "goal": 8,
                "skill": 6, "preference": 6,
                "person": 5, "fact": 5
            }
            importance = type_importance.get(memory_type, 5)

            embedding = self.embedding_service.generate_embedding(content)

            if embedding is None:
                return (
                    "I couldn't store that memory because "
                    "embeddings are unavailable."
                )

            self.memory_repo.create(
                memory_type,
                content,
                embedding,
                category=memory_type,
                importance=importance,
                agent_id=agent_id
            )

            return f"Stored {memory_type} memory."

        content = raw.strip()
        if not content:
            return "No memory content provided."

        embedding = self.embedding_service.generate_embedding(content)

        if embedding is None:
            return (
                "I couldn't store that memory because "
                "embeddings are unavailable."
            )

        self.memory_repo.create(
            "fact",
            content,
            embedding,
            importance=5,
            agent_id=agent_id
        )

        return "Memory stored."

    def list_memories(self, agent_id=None):

        
        memories = self.memory_repo.get_all(agent_id=agent_id)

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
        query,
        agent_id=None
    ):

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                query,
                limit=self.retrieval_limit,
                agent_id=agent_id
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
            query_embedding,
            agent_id=agent_id
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
        query,
        agent_id=None
    ):

        if self.retrieval_service:

            result = self.retrieval_service.retrieve(
                query,
                limit=self.retrieval_limit,
                agent_id=agent_id
            )

            if isinstance(result, str):
                return []

            return result

        query_embedding = (
            self.embedding_service
            .generate_embedding(query)
        )

        if not query_embedding:
            return []

        memories = (
            self.memory_repo
            .semantic_search(
                query_embedding,
                agent_id=agent_id
            )
        )

        return memories
