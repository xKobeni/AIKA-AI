from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass
class RankedSource:

    title: str
    url: str
    snippet: str
    score: float
    source_type: str


class SourceRanker:

    DOMAIN_PATTERNS = [
        ("docs.", "official_docs", 10),
        ("readthedocs", "official_docs", 10),
        ("documentation", "official_docs", 10),
        ("learn.microsoft", "official_docs", 10),
        ("developer.mozilla", "official_docs", 10),
        ("github.com", "github", 9),
        ("wikipedia.org", "wikipedia", 7),
        ("medium.com", "blog", 5),
        ("dev.to", "blog", 5),
        ("hashnode", "blog", 5),
        ("stackoverflow.com", "forum", 3),
        ("reddit.com", "forum", 3),
        ("news.ycombinator", "forum", 3),
        ("twitter.com", "forum", 3),
        ("x.com", "forum", 3),
    ]

    def rank(self, sources):
        if not sources:
            return []

        ranked = []

        for s in sources:
            title = s.get("title", "")
            url = s.get("url", "")
            snippet = s.get("snippet", "")
            source_type, score = self._classify_url(url)

            ranked.append(
                RankedSource(
                    title=title,
                    url=url,
                    snippet=snippet,
                    score=score,
                    source_type=source_type,
                )
            )

        ranked.sort(key=lambda x: x.score, reverse=True)

        return ranked

    def select_top(self, ranked, n=3):
        if not ranked:
            return []

        return ranked[:n]

    def _classify_url(self, url):
        domain = urlparse(url).netloc.lower()

        for pattern, source_type, score in self.DOMAIN_PATTERNS:
            if pattern in domain:
                return source_type, score

        return "unknown", 4
