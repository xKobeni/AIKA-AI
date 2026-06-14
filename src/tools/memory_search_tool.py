from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class MemorySearchTool(BaseTool):

    description = "Searches stored memories using semantic search"
    category = ToolCategory.MEMORY
    permission = ToolPermission.LOW

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

        return {
            "success": True,
            "memories": [
                memory.content
                for memory in memories
            ]
        }