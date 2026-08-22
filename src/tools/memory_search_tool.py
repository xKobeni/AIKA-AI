from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class MemorySearchTool(BaseTool):

    description = "Searches stored memories using semantic search"
    category = ToolCategory.MEMORY
    permission = ToolPermission.LOW

    def __init__(
        self,
        retrieval_service
    ):

        self.retrieval_service = retrieval_service
        self.retrieval_limit = settings.memory_retrieval_limit

    def refresh_from_settings(self):
        self.retrieval_limit = settings.memory_retrieval_limit

    @property
    def name(self):

        return "memory_search"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "What to search for in memories"
                }
            }
        }

    def execute(
        self,
        query
    ):

        result = self.retrieval_service.retrieve(
            query,
            limit=self.retrieval_limit
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
