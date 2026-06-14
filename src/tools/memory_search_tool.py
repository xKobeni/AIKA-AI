from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class MemorySearchTool(BaseTool):

    description = "Searches stored memories using semantic search"
    category = ToolCategory.MEMORY
    permission = ToolPermission.LOW

    def __init__(
        self,
        retrieval_service
    ):

        self.retrieval_service = retrieval_service

    @property
    def name(self):

        return "memory_search"

    def execute(
        self,
        query
    ):

        result = self.retrieval_service.retrieve(
            query,
            limit=5
        )

        if isinstance(result, str):
            return {
                "success": True,
                "memories": [result]
            }

        return {
            "success": True,
            "memories": [
                memory.content
                for memory in result
            ]
        }