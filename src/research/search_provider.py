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

        except Exception as e:

            print(f"[DDGSProvider] Search error: {e}")
            return []
