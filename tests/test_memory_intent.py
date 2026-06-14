import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from memory.memory_intent import (
    MemoryIntent,
    MemoryIntentAnalyzer
)

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


print("=== Test: MemoryIntentAnalyzer ===\n")

analyzer = MemoryIntentAnalyzer()

# Test 1: Goal detection
print("[Test 1: Goal intent detection]")

check(
    "what are my goals",
    analyzer.detect_intent("what are my goals")
    == MemoryIntent.GOAL
)

check(
    "my objectives",
    analyzer.detect_intent("my objectives")
    == MemoryIntent.GOAL
)

check(
    "what do i want to achieve",
    analyzer.detect_intent("what do i want to achieve")
    == MemoryIntent.GOAL
)

check(
    "target for this year",
    analyzer.detect_intent("target for this year")
    == MemoryIntent.GOAL
)

# Test 2: Project detection
print("\n[Test 2: Project intent detection]")

check(
    "what project am i building",
    analyzer.detect_intent("what project am i building")
    == MemoryIntent.PROJECT
)

check(
    "what am i working on",
    analyzer.detect_intent("what am i working on")
    == MemoryIntent.PROJECT
)

check(
    "what are you developing",
    analyzer.detect_intent("what are you developing")
    == MemoryIntent.PROJECT
)

check(
    "what am i creating",
    analyzer.detect_intent("what am i creating")
    == MemoryIntent.PROJECT
)

# Test 3: Preference detection
print("\n[Test 3: Preference intent detection]")

check(
    "what are my preferences",
    analyzer.detect_intent("what are my preferences")
    == MemoryIntent.PREFERENCE
)

check(
    "what do i like",
    analyzer.detect_intent("what do i like")
    == MemoryIntent.PREFERENCE
)

check(
    "what are my hobbies",
    analyzer.detect_intent("what are my hobbies")
    == MemoryIntent.PREFERENCE
)

check(
    "what are my interests",
    analyzer.detect_intent("what are my interests")
    == MemoryIntent.PREFERENCE
)

# Test 4: Skill detection
print("\n[Test 4: Skill intent detection]")

check(
    "what skills do i have",
    analyzer.detect_intent("what skills do i have")
    == MemoryIntent.SKILL
)

check(
    "what am i good at",
    analyzer.detect_intent("what am i good at")
    == MemoryIntent.SKILL
)

check(
    "my experience with python",
    analyzer.detect_intent("my experience with python")
    == MemoryIntent.SKILL
)

# Test 5: Person detection
print("\n[Test 5: Person intent detection]")

check(
    "tell me about my family",
    analyzer.detect_intent("tell me about my family")
    == MemoryIntent.PERSON
)

check(
    "who are my friends",
    analyzer.detect_intent("who are my friends")
    == MemoryIntent.PERSON
)

# Test 6: General fallback
print("\n[Test 6: General fallback]")

check(
    "hello",
    analyzer.detect_intent("hello")
    == MemoryIntent.GENERAL
)

check(
    "how are you",
    analyzer.detect_intent("how are you")
    == MemoryIntent.GENERAL
)

check(
    "tell me a joke",
    analyzer.detect_intent("tell me a joke")
    == MemoryIntent.GENERAL
)

check(
    "empty string",
    analyzer.detect_intent("")
    == MemoryIntent.GENERAL
)

check(
    "None",
    analyzer.detect_intent(None)
    == MemoryIntent.GENERAL
)

# Test 7: PROFILE intent detection
print("\n[Test 7: PROFILE intent detection]")

check(
    "what do you know about me",
    analyzer.detect_intent(
        "what do you know about me"
    ) == MemoryIntent.PROFILE
)

check(
    "tell me about myself",
    analyzer.detect_intent(
        "tell me about myself"
    ) == MemoryIntent.PROFILE
)

check(
    "who am i",
    analyzer.detect_intent("who am i")
    == MemoryIntent.PROFILE
)

check(
    "summarize me",
    analyzer.detect_intent("summarize me")
    == MemoryIntent.PROFILE
)

check(
    "hello is not profile",
    analyzer.detect_intent("hello")
    != MemoryIntent.PROFILE
)

check(
    "goals is not profile",
    analyzer.detect_intent("what are my goals")
    != MemoryIntent.PROFILE
)

# Test 8: Profile overrides person keyword
print("\n[Test 8: Profile takes priority over PERSON]")

check(
    "know about me is PROFILE not PERSON",
    analyzer.detect_intent(
        "what do you know about me"
    ) == MemoryIntent.PROFILE
)

# Test 9: Target categories
print("\n[Test 9: Target categories mapping]")

check(
    "GOAL maps to goal",
    analyzer.get_target_categories(MemoryIntent.GOAL)
    == ["goal"]
)

check(
    "PROJECT maps to project",
    analyzer.get_target_categories(MemoryIntent.PROJECT)
    == ["project"]
)

check(
    "GENERAL maps to empty",
    analyzer.get_target_categories(MemoryIntent.GENERAL)
    == []
)

check(
    "PROFILE maps to all categories",
    len(
        analyzer.get_target_categories(
            MemoryIntent.PROFILE
        )
    ) >= 4
)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
