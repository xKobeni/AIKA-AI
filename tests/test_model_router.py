import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from unittest.mock import patch
from brain.model_router import ModelRouter

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


print("=== Test ModelRouter ===\n")

with patch("brain.model_router.settings") as mock_settings:
    mock_settings.fast_model = "qwen2.5:3b"
    mock_settings.smart_model = "llama3:8b"

    router = ModelRouter()

    check(
        "fast model loaded",
        router.fast == "qwen2.5:3b"
    )

    check(
        "smart model loaded",
        router.smart == "llama3:8b"
    )

    # Intent classification always fast
    check(
        "intent task -> fast",
        router.select("hello", task_type="intent") == "qwen2.5:3b"
    )

    check(
        "reflection task -> fast",
        router.select("analyze results", task_type="reflection") == "qwen2.5:3b"
    )

    check(
        "tool_result_summarize -> fast",
        router.select("summarize this", task_type="tool_result_summarize") == "qwen2.5:3b"
    )

    # Plan/report always smart
    check(
        "plan task -> smart",
        router.select("hello", task_type="plan") == "llama3:8b"
    )

    check(
        "report task -> smart",
        router.select("hello", task_type="report") == "llama3:8b"
    )

    check(
        "file_content task -> smart",
        router.select("hello", task_type="file_content") == "llama3:8b"
    )

    # Simple chat -> fast
    check(
        "simple greeting -> fast",
        router.select("hello") == "qwen2.5:3b"
    )

    check(
        "simple question -> fast",
        router.select("what time is it") == "qwen2.5:3b"
    )

    check(
        "single word -> fast",
        router.select("hi") == "qwen2.5:3b"
    )

    # Complex keywords -> smart
    check(
        "analyze keyword -> smart",
        router.select("analyze the codebase") == "llama3:8b"
    )

    check(
        "research keyword -> smart",
        router.select("research AI trends") == "llama3:8b"
    )

    check(
        "write code keyword -> smart",
        router.select("write code to sort a list") == "llama3:8b"
    )

    check(
        "debug keyword -> smart",
        router.select("debug this error") == "llama3:8b"
    )

    check(
        "refactor keyword -> smart",
        router.select("refactor this function") == "llama3:8b"
    )

    # Multi-step tasks -> smart
    check(
        "find and ... -> smart",
        router.select("find and read the main file") == "llama3:8b"
    )

    check(
        "search and ... -> smart",
        router.select("search and summarize results") == "llama3:8b"
    )

    # Long messages -> smart
    long_message = " ".join(["word"] * 25)
    check(
        "long message (25 words) -> smart",
        router.select(long_message) == "llama3:8b"
    )

    # Complex questions -> smart
    check(
        "complex question -> smart",
        router.select("how does the authentication system work in this codebase") == "llama3:8b"
    )

    # Iteration escalation
    check(
        "iteration 0 -> fast",
        router.select("hello", iteration=0) == "qwen2.5:3b"
    )

    check(
        "iteration 1 -> fast",
        router.select("hello", iteration=1) == "qwen2.5:3b"
    )

    check(
        "iteration 2 -> smart (escalation)",
        router.select("hello", iteration=2) == "llama3:8b"
    )

    check(
        "iteration 3 -> smart (escalation)",
        router.select("hello", iteration=3) == "llama3:8b"
    )

    # Escalate method
    check(
        "escalate() returns smart",
        router.escalate("tool failed") == "llama3:8b"
    )

    # get_status
    status = router.get_status()
    check(
        "get_status has fast",
        status["fast"] == "qwen2.5:3b"
    )

    check(
        "get_status has smart",
        status["smart"] == "llama3:8b"
    )


print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
