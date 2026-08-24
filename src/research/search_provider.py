import logging


logger = logging.getLogger(__name__)


class SearchProviderError(RuntimeError):
    """Typed provider failure that carries only safe internal classification."""

    def __init__(self, error_type="SearchProviderError", *, provider="search"):
        error_type = str(error_type or "SearchProviderError")[:100]
        provider = str(provider or "search")[:50]
        self.error_type = (
            error_type if error_type.isidentifier() else "SearchProviderError"
        )
        self.provider = provider if provider.isidentifier() else "search"
        super().__init__("Search provider unavailable")


class SearchProvider:

    def search(
        self,
        query,
        max_results=5
    ):
        raise NotImplementedError


class DDGSProvider(SearchProvider):

    def search(
        self,
        query,
        max_results=5
    ):

        try:

            from ddgs import DDGS

            with DDGS() as ddgs:

                results = []

                for i, r in enumerate(
                    ddgs.text(
                        query,
                        max_results=max_results
                    )
                ):

                    if i >= max_results:
                        break

                    results.append({
                        "title": r.get("title", ""),
                        "url": r.get("href", ""),
                        "snippet": r.get("body", "")
                    })

                return results

        except Exception as exc:
            error_type = type(exc).__name__
            logger.warning(
                "DDGS search provider failed | error_type=%s",
                error_type,
            )
            raise SearchProviderError(
                error_type,
                provider="ddgs",
            ) from exc
