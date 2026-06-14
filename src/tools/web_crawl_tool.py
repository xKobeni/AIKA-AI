from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class WebCrawlTool(BaseTool):

    description = (
        "Fetches a webpage and extracts "
        "clean text content"
    )
    category = ToolCategory.WEB
    permission = ToolPermission.MEDIUM

    @property
    def name(self):

        return "web_crawl"

    def execute(
        self,
        url
    ):

        try:

            result = self._crawl(url)

            return result

        except Exception as e:

            return {
                "success": False,
                "content": "",
                "url": url,
                "error": f"Crawl failed: {e}"
            }

    def _crawl(
        self,
        url
    ):

        from crawl4ai import AsyncWebCrawler
        import asyncio

        async def fetch():

            async with AsyncWebCrawler() as crawler:

                result = await crawler.arun(
                    url=url
                )

                return result

        try:

            loop = asyncio.get_event_loop()

        except RuntimeError:

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        crawl_result = loop.run_until_complete(
            fetch()
        )

        markdown = getattr(
            crawl_result,
            "markdown",
            None
        )

        if markdown:

            return {
                "success": True,
                "content": markdown,
                "url": url,
                "title": getattr(
                    crawl_result,
                    "title",
                    ""
                )
            }

        extracted = getattr(
            crawl_result,
            "extracted_content",
            None
        )

        if extracted:

            return {
                "success": True,
                "content": extracted,
                "url": url,
                "title": ""
            }

        return {
            "success": False,
            "content": "",
            "url": url,
            "error": "No content extracted"
        }
