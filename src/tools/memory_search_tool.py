from tools.base_tool import BaseTool


class MemorySearchTool(BaseTool):

    def __init__(
        self,
        memory_repository
    ):
        self.memory_repository = (
            memory_repository
        )

    @property
    def name(self):

        return "memory_search"

    def execute(
        self,
        query
    ):

        results = (
            self.memory_repository
            .semantic_search(query)
        )

        return results