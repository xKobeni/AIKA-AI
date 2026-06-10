from tools.base_tool import BaseTool


class MemorySearchTool(BaseTool):

    def __init__(
        self,
        memory_repository,
        embedding_service
    ):

        self.memory_repository = (
            memory_repository
        )

        self.embedding_service = (
            embedding_service
        )

    @property
    def name(self):

        return "memory_search"

    def execute(
        self,
        query
    ):

        query_embedding = (
            self.embedding_service
            .generate_embedding(query)
        )

        memories = (
            self.memory_repository
            .semantic_search(
                query_embedding
            )
        )

        return [
            memory.content
            for memory in memories
        ]