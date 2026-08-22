from concurrent.futures import ThreadPoolExecutor

from config.settings import settings
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from tools.url_security import URLSecurityError, fetch_public_url


class WebCrawlTool(BaseTool):

    description = (
        "Fetches one or more webpages and extracts "
        "clean text content from each"
    )
    category = ToolCategory.WEB
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.refresh_from_settings()

    def refresh_from_settings(self):
        workers = getattr(settings, "web_crawl_max_workers", 4)
        max_urls = getattr(settings, "web_crawl_max_urls", 10)
        self.max_workers = workers if isinstance(workers, int) else 4
        self.max_urls = max_urls if isinstance(max_urls, int) else 10
        self.max_redirects = getattr(settings, "web_crawl_max_redirects", 5)
        self.timeout = getattr(settings, "web_crawl_timeout", 15)
        self.max_response_bytes = getattr(
            settings, "web_crawl_max_response_bytes", 5_000_000
        )
        self.allow_private_network = getattr(
            settings, "web_crawl_allow_private_network", False
        ) is True

    @property
    def name(self):

        return "web_crawl"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "urls": {
                    "type": "string",
                    "required": True,
                    "description": "URL or list of URLs to crawl"
                }
            }
        }

    def execute(
        self,
        urls
    ):

        try:

            if isinstance(urls, str):

                result = self._crawl(urls)

                return result

            if isinstance(urls, list):
                urls = urls[:max(1, self.max_urls)]
                if not urls:
                    return {
                        "success": False, "pages": [], "total": 0,
                        "crawled": 0, "error": "No URLs provided"
                    }
                worker_count = min(max(1, self.max_workers), len(urls))
                with ThreadPoolExecutor(max_workers=worker_count) as executor:
                    crawl_results = list(executor.map(self._crawl, urls))

                pages = []
                for url, crawl_result in zip(urls, crawl_results):

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

        from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
        import asyncio

        try:
            final_url, html = fetch_public_url(
                url,
                allow_private=self.allow_private_network,
                max_redirects=self.max_redirects,
                timeout=self.timeout,
                max_bytes=self.max_response_bytes,
            )
        except URLSecurityError as e:
            return {
                "success": False, "content": "", "url": url,
                "error": f"URL blocked: {e}"
            }
        except Exception as e:
            return {
                "success": False, "content": "", "url": url,
                "error": f"Fetch failed: {e}"
            }

        async def fetch():

            async with AsyncWebCrawler() as crawler:

                result = await crawler.arun(
                    url=f"raw:{html}",
                    config=CrawlerRunConfig(base_url=final_url),
                )

                return result

        crawl_result = asyncio.run(fetch())

        markdown = getattr(
            crawl_result,
            "markdown",
            None
        )

        if markdown:

            return {
                "success": True,
                "content": markdown,
                "url": final_url,
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
                "url": final_url,
                "title": ""
            }

        return {
            "success": False,
            "content": "",
            "url": final_url,
            "error": "No content extracted"
        }
