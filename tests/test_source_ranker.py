import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from research.source_ranker import SourceRanker, RankedSource

passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} {detail}")
        failed += 1


print("=== Test: SourceRanker ===\n")

ranker = SourceRanker()

# Test 1: Empty input
print("[Test 1: Empty input]")

result = ranker.rank([])

check("returns empty list for None/empty", result == [])

result = ranker.rank(None)

check("handles None gracefully", result == [])

# Test 2: URL classification
print("\n[Test 2: URL classification]")

tests = [
    (
        "https://docs.pgvector.org",
        "official_docs",
        10
    ),
    (
        "https://github.com/pgvector/pgvector",
        "github",
        9
    ),
    (
        "https://en.wikipedia.org/wiki/Pgvector",
        "wikipedia",
        7
    ),
    (
        "https://medium.com/article",
        "blog",
        5
    ),
    (
        "https://stackoverflow.com/questions",
        "forum",
        3
    ),
    (
        "https://example.com/random",
        "unknown",
        4
    ),
]

for url, expected_type, expected_score in tests:

    source_type, score = ranker._classify_url(url)

    check(
        f"classifies {url[:30]}...",
        source_type == expected_type
        and score == expected_score,
        f"got ({source_type}, {score}) "
        f"expected ({expected_type}, {expected_score})"
    )

# Test 3: Ranking order
print("\n[Test 3: Ranking order]")

sources = [
    {
        "title": "Random Blog",
        "url": "https://medium.com/pgvector-intro",
        "snippet": "Blog about pgvector"
    },
    {
        "title": "Official Docs",
        "url": "https://docs.pgvector.org",
        "snippet": "Official documentation"
    },
    {
        "title": "GitHub Repo",
        "url": "https://github.com/pgvector/pgvector",
        "snippet": "Source code"
    },
    {
        "title": "Wikipedia",
        "url": "https://en.wikipedia.org/wiki/Pgvector",
        "snippet": "Wikipedia article"
    },
]

ranked = ranker.rank(sources)

check(
    "ranked has 4 items",
    len(ranked) == 4
)

check(
    "official docs is first",
    ranked[0].source_type == "official_docs"
)

check(
    "github is second",
    ranked[1].source_type == "github"
)

check(
    "wikipedia is third",
    ranked[2].source_type == "wikipedia"
)

check(
    "blog is fourth",
    ranked[3].source_type == "blog"
)

check(
    "scores are descending",
    ranked[0].score >= ranked[1].score >= ranked[2].score >= ranked[3].score
)

# Test 4: Top-N selection
print("\n[Test 4: Top-N selection")

top = ranker.select_top(ranked, n=3)

check("select_top returns 3 items", len(top) == 3)

check(
    "first is official_docs",
    top[0].source_type == "official_docs"
)

check(
    "second is github",
    top[1].source_type == "github"
)

check(
    "third is wikipedia",
    top[2].source_type == "wikipedia"
)

top_2 = ranker.select_top(ranked, n=2)

check("select_top with n=2 returns 2", len(top_2) == 2)

top_10 = ranker.select_top(ranked, n=10)

check(
    "select_top with n>available returns all",
    len(top_10) == 4
)

empty_top = ranker.select_top([], n=3)

check("select_top with empty returns empty", empty_top == [])

# Test 5: RankedSource dataclass
print("\n[Test 5: RankedSource dataclass")

rs = RankedSource(
    title="Test",
    url="https://test.com",
    snippet="A test source",
    score=9.0,
    source_type="github"
)

check("title is set", rs.title == "Test")
check("url is set", rs.url == "https://test.com")
check("snippet is set", rs.snippet == "A test source")
check("score is set", rs.score == 9.0)
check("source_type is set", rs.source_type == "github")

# Test 6: Result from rank lists
print("\n[Test 6: Ranks from wrong order")

reversed_sources = [
    {
        "title": "Forum Post",
        "url": "https://reddit.com/r/pgvector",
        "snippet": "Discussion"
    },
    {
        "title": "Official Docs",
        "url": "https://docs.example.com",
        "snippet": "Documentation"
    },
]

ranked = ranker.rank(reversed_sources)

check("official docs ranked first", ranked[0].source_type == "official_docs")

check("forum ranked second", ranked[1].source_type == "forum")

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
