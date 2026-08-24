import logging

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from research.search_provider import DDGSProvider, SearchProviderError


logger = logging.getLogger(__name__)

SEARCH_OUTCOME_RESULTS = "results"
SEARCH_OUTCOME_NO_RESULTS = "no_results"
SEARCH_OUTCOME_PROVIDER_ERROR = "provider_error"
NO_RESULTS_MESSAGE = "No matching results were found."
PROVIDER_UNAVAILABLE_MESSAGE = (
    "The web-search provider is currently unavailable."
)


class WebSearchTool(BaseTool):

    description = (
        "Searches the web for information "
        "using DuckDuckGo"
    )
    category = ToolCategory.WEB
    permission = ToolPermission.MEDIUM
    response_policy = "synthesize"

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

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "Search query"
                },
                "max_results": {
                    "type": "integer",
                    "required": False,
                    "default": 5,
                    "description": "Maximum number of results"
                }
            }
        }

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
                    "success": True,
                    "outcome": SEARCH_OUTCOME_NO_RESULTS,
                    "results": [],
                    "message": NO_RESULTS_MESSAGE,
                }

            return {
                "success": True,
                "outcome": SEARCH_OUTCOME_RESULTS,
                "results": results
            }

        except SearchProviderError as exc:
            logger.warning(
                "Web search unavailable | provider=%s error_type=%s",
                exc.provider,
                exc.error_type,
            )
            return {
                "success": False,
                "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
                "results": [],
                "error": PROVIDER_UNAVAILABLE_MESSAGE,
                "error_type": exc.error_type,
            }

        except Exception as exc:
            error_type = type(exc).__name__
            logger.warning(
                "Unexpected web search provider failure | error_type=%s",
                error_type,
            )
            return {
                "success": False,
                "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
                "results": [],
                "error": PROVIDER_UNAVAILABLE_MESSAGE,
                "error_type": error_type,
            }
