import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from research.content_processor import ContentProcessor

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


print("=== Test: ContentProcessor ===\n")

cp = ContentProcessor()

# Test 1: Empty input
print("[Test 1: Empty input]")

result = cp.process([])
check("returns empty string for no pages", result == "")

result = cp.process(None)
check("returns empty string for None", result == "")

# Test 2: Single page
print("\n[Test 2: Single page]")

pages = [
    {
        "url": "https://example.com",
        "content": "This is page one content"
    }
]

result = cp.process(pages)
check("contains source marker", "Source 1" in result)
check("contains page content", "page one content" in result)

# Test 3: Multiple pages
print("\n[Test 3: Multiple pages]")

pages = [
    {"url": "https://example.com/1", "content": "First page"},
    {"url": "https://example.com/2", "content": "Second page"}
]

result = cp.process(pages)
check("contains first source", "Source 1" in result)
check("contains second source", "Source 2" in result)
check("contains first content", "First page" in result)
check("contains second content", "Second page" in result)

# Test 4: Deduplication
print("\n[Test 4: Deduplication]")

pages = [
    {"url": "https://example.com/1", "content": "Duplicate line\nUnique line"},
    {"url": "https://example.com/2", "content": "Duplicate line\nAnother unique"}
]

result = cp.process(pages)
lines = result.splitlines()
duplicate_count = sum(
    1 for line in lines
    if line.strip().lower() == "duplicate line"
)
check(
    "deduplicates repeated lines across sources",
    duplicate_count <= 2
)

# Test 5: Cleaning
print("\n[Test 5: Cleaning]")

pages = [
    {
        "url": "https://example.com",
        "content": "Word1  Word2\n\n\n\nWord3"
    }
]

result = cp.process(pages)
check("collapses multiple spaces", "  " not in result)
check("collapses excess newlines", "\n\n\n" not in result)
check("result is stripped", result == result.strip())

# Test 6: Mix of dict and non-dict pages
print("\n[Test 6: Mixed input types]")

result = cp.process([
    {"url": "x", "content": "Dict content"},
    "Plain string content"
])
check("handles dict pages", "Dict content" in result)
check("handles plain string pages", "Plain string content" in result)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
