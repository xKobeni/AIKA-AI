import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from tools.web_search_tool import WebSearchTool

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


print("=== Test: WebSearchTool ===\n")


class MockProvider:

    def search(self, query, max_results=5):

        return [
            {
                "title": "Test Result",
                "url": "https://example.com/test",
                "snippet": "This is a test snippet"
            }
        ]


class FailingProvider:

    def search(self, query, max_results=5):
        raise Exception("Search API unavailable")


# Test 1: Successful search
print("[Test 1: Successful search]")

tool = WebSearchTool(provider=MockProvider())
result = tool.execute("test query", max_results=3)

check("returns a dict", isinstance(result, dict))
check("success is True", result.get("success") is True)
check("results is a list", isinstance(result.get("results"), list))
check("has title in first result", "title" in result["results"][0])
check("has url in first result", "url" in result["results"][0])
check("has snippet in first result", "snippet" in result["results"][0])
check("url is correct", result["results"][0]["url"] == "https://example.com/test")

# Test 2: Provider error
print("\n[Test 2: Provider error]")

tool = WebSearchTool(provider=FailingProvider())
result = tool.execute("test query")

check("returns a dict on error", isinstance(result, dict))
check("success is False on error", result.get("success") is False)
check("has error message", "error" in result)

# Test 3: No results
print("\n[Test 3: No results]")


class EmptyProvider:

    def search(self, query, max_results=5):
        return []


tool = WebSearchTool(provider=EmptyProvider())
result = tool.execute("nonexistent query")

check("returns dict when no results", isinstance(result, dict))
check("success is False when no results", result.get("success") is False)
check("results is empty list", result.get("results") == [])

# Test 4: Tool metadata
print("\n[Test 4: Tool metadata]")

tool = WebSearchTool()
check("name is web_search", tool.name == "web_search")
check(
    "description is set",
    len(tool.description) > 0
)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
