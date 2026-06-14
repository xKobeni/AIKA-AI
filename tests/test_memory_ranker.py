import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from memory.memory_intent import MemoryIntent
from memory.memory_ranker import MemoryRanker

passed = 0
failed = 0


class MockMemory:

    def __init__(
        self,
        content,
        category,
        _score=0.0,
        importance=5,
        access_count=0,
    ):
        self.content = content
        self.category = category
        self._score = _score
        self.importance = importance
        self.access_count = access_count
        self.id = hash(content)


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} {detail}")
        failed += 1


print("=== Test: MemoryRanker ===\n")

ranker = MemoryRanker()

# Test 1: Empty input
print("[Test 1: Empty input]")

result = ranker.rank([], MemoryIntent.GENERAL)

check("returns empty list for empty", result == [])

result = ranker.rank(None, MemoryIntent.GENERAL)

check("handles None gracefully", result == [])

# Test 2: Ranking boosts target category
print("\n[Test 2: Dynamic boost for goal intent]")

memories = [
    MockMemory(
        "Developing AIKA",
        "project",
        _score=0.40
    ),
    MockMemory(
        "Lose Weight",
        "goal",
        _score=0.35
    ),
    MockMemory(
        "User likes Anime",
        "preference",
        _score=0.30
    ),
]

ranked = ranker.rank(memories, MemoryIntent.GOAL)

check("3 results returned", len(ranked) == 3)

check(
    "goal memory is first",
    ranked[0].category == "goal"
)

check(
    "goal memory content is correct",
    ranked[0].content == "Lose Weight"
)

# Test 3: Project intent
print("\n[Test 3: Dynamic boost for project intent]")

ranked = ranker.rank(memories, MemoryIntent.PROJECT)

check("project memory is first", ranked[0].category == "project")

check("goal memory is second", ranked[1].category == "goal")

# Test 4: Preference intent
print("\n[Test 4: Dynamic boost for preference intent]")

ranked = ranker.rank(memories, MemoryIntent.PREFERENCE)

check(
    "preference memory is first",
    ranked[0].category == "preference"
)

# Test 5: GENERAL intent no boost
print("\n[Test 5: General intent no boost]")

ranked = ranker.rank(memories, MemoryIntent.GENERAL)

check(
    "original order preserved for general",
    ranked[0].category == "project"
)

check(
    "second is goal for general",
    ranked[1].category == "goal"
)

# Test 6: Intent filtering
print("\n[Test 6: Intent filtering")

memories_mixed = [
    MockMemory("Project A", "project", _score=0.9),
    MockMemory("Goal A", "goal", _score=0.8),
    MockMemory("Preference A", "preference", _score=0.7),
]

filtered = ranker.filter_by_intent(
    memories_mixed,
    MemoryIntent.GOAL
)

check(
    "goal filter returns only goals",
    all(m.category == "goal" for m in filtered)
)

check(
    "goal filter returns 1 result",
    len(filtered) == 1
)

check(
    "goal filter correct content",
    filtered[0].content == "Goal A"
)

filtered = ranker.filter_by_intent(
    memories_mixed,
    MemoryIntent.PROJECT
)

check(
    "project filter returns only projects",
    all(m.category == "project" for m in filtered)
)

filtered = ranker.filter_by_intent(
    memories_mixed,
    MemoryIntent.PREFERENCE
)

check(
    "preference filter returns only preferences",
    all(m.category == "preference" for m in filtered)
)

# GENERAL passes through
filtered = ranker.filter_by_intent(
    memories_mixed,
    MemoryIntent.GENERAL
)

check(
    "general filter keeps all categories",
    len(filtered) == 3
)

# PROFILE passes through
filtered = ranker.filter_by_intent(
    memories_mixed,
    MemoryIntent.PROFILE
)

check(
    "profile filter keeps all categories",
    len(filtered) == 3
)

# Empty filtered result falls back to unfiltered
only_projects = [
    MockMemory("Only Project", "project", _score=0.5)
]

filtered = ranker.filter_by_intent(
    only_projects,
    MemoryIntent.GOAL
)

check(
    "fallback when no goals exist",
    len(filtered) == 1
)

check(
    "fallback preserves original",
    filtered[0].category == "project"
)

# Empty input
check(
    "empty input",
    ranker.filter_by_intent([], MemoryIntent.GOAL) == []
)

check(
    "None input",
    ranker.filter_by_intent(None, MemoryIntent.GOAL) == []
)

# Test 7: Diversity filter
print("\n[Test 7: Diversity filter]")

many_memories = [
    MockMemory("Project 1", "project", _score=0.9),
    MockMemory("Project 2", "project", _score=0.8),
    MockMemory("Project 3", "project", _score=0.7),
    MockMemory("Goal 1", "goal", _score=0.6),
    MockMemory("Goal 2", "goal", _score=0.5),
    MockMemory("Preference 1", "preference", _score=0.4),
]

diverse = ranker.apply_diversity(many_memories, max_per_category=2)

check("diverse has 5 items", len(diverse) == 5)

project_count = sum(
    1 for m in diverse if m.category == "project"
)

check(
    "at most 2 projects",
    project_count == 2
)

goal_count = sum(
    1 for m in diverse if m.category == "goal"
)

check("at most 2 goals", goal_count == 2)

check(
    "preference included",
    any(
        m.category == "preference"
        for m in diverse
    )
)

# Test 8: Empty/None diversity
print("\n[Test 8: Empty/None diversity]")

check(
    "empty list in",
    ranker.apply_diversity([]) == []
)

check(
    "None in",
    ranker.apply_diversity(None) == []
)

# Test 9: Default max_per_category
print("\n[Test 9: Default max_per_category]")

check(
    "default is 2",
    ranker.MAX_PER_CATEGORY == 2
)

# Test 10: Intent category mapping
print("\n[Test 10: Intent category mapping]")

check(
    "GOAL maps to goal",
    "goal" in ranker.INTENT_CATEGORY_MAP[MemoryIntent.GOAL]
)

check(
    "PROJECT maps to project",
    "project" in ranker.INTENT_CATEGORY_MAP[MemoryIntent.PROJECT]
)

check(
    "GENERAL maps to empty",
    ranker.INTENT_CATEGORY_MAP[MemoryIntent.GENERAL] == set()
)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
