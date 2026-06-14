from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class WebCrawlTool(BaseTool):

    description = (
        "Fetches one or more webpages and extracts "
        "clean text content from each"
    )
    category = ToolCategory.WEB
    permission = ToolPermission.MEDIUM

    @property
    def name(self):

        return "web_crawl"

    def execute(
        self,
        urls
    ):

        try:

            if isinstance(urls, str):

                result = self._crawl(urls)

                return result

            if isinstance(urls, list):

                pages = []

                for url in urls:

                    crawl_result = self._crawl(url)

                    pages.append({
                        "url": crawl_result.get("url", url),
                        "title": crawl_result.get("title", ""),
                        "content": crawl_result.get("content", ""),
                        "success": crawl_result.get("success", False),
                        "error": crawl_result.get("error", "")
                    })

                successful = [
                    p for p in pages if p.get("success")
                ]

                return {
                    "success": len(successful) > 0,
                    "pages": pages,
                    "total": len(urls),
                    "crawled": len(successful)
                }

            return {
                "success": False,
                "pages": [],
                "error": "urls must be a string or list of strings"
            }

        except Exception as e:

            return {
                "success": False,
                "pages": [],
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
