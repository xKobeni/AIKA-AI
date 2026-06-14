from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from research.search_provider import DDGSProvider


class WebSearchTool(BaseTool):

    description = (
        "Searches the web for information "
        "using DuckDuckGo"
    )
    category = ToolCategory.WEB
    permission = ToolPermission.MEDIUM

    def __init__(
        self,
        provider=None
    ):

        self.provider = (
            provider or DDGSProvider()
        )

    @property
    def name(self):

        return "web_search"

    def execute(
        self,
        query,
        max_results=5
    ):

        try:

            results = self.provider.search(
                query,
                max_results=max_results
            )

            if not results:

                return {
                    "success": False,
                    "results": [],
                    "error": (
                        "No search results found. "
                        "Try a different query."
                    )
                }

            return {
                "success": True,
                "results": results
            }

        except Exception as e:

            return {
                "success": False,
                "results": [],
                "error": f"Search failed: {e}"
            }
