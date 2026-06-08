from repositories.memory_repository import MemoryRepository

class MemoryHandler:

    def __init__(self, memory_repo, embedding_service):

        self.memory_repo = memory_repo
        self.embedding_service = embedding_service

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
            
            embedding = self.embedding_service.generate_embedding(content)

            self.memory_repo.create(
                memory_type.strip(),
                content.strip(),
                embedding
            )

            return (
                f"Stored "
                f"{memory_type.strip()} memory."
            )

        self.memory_repo.create(
            "fact",
            raw.strip()
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

        results = self.memory_repo.search(
            query
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