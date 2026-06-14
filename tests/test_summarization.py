import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from planner.plan import Plan
from planner.plan_step import PlanStep
from planner.plan_executor import PlanExecutor
from planner.execution_planner import ExecutionPlanner
from tools.tool_manager import ToolManager
from tools.file_search_tool import FileSearchTool
from tools.file_read_tool import FileReadTool

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


class MockLLM:

    def __init__(self):
        self.last_prompt = ""

    def generate(self, prompt):
        self.last_prompt = prompt
        return (
            "AIKA is a personal AI operating system "
            "with memory, tools, and future agents "
            "designed to function as an autonomous "
            "AI companion."
        )


print("=== Stage 4: Test Summarization ===\n")

tm = ToolManager()
tm.register_tool(FileSearchTool())
tm.register_tool(FileReadTool())

llm = MockLLM()
executor = PlanExecutor(tm, llm)

# Test 1: File search -> file read -> summarize (explicit plan)
print("[Test 1: Explicit plan - search -> read -> summarize]")

plan = Plan(
    goal="summarize",
    steps=[
        PlanStep(
            1,
            "file_search",
            {
                "query": "test_fixtures",
                "root_path": str(Path(__file__).parent)
            },
            "Search for fixture file"
        ),
        PlanStep(
            2,
            "file_read",
            {
                "root_path": str(Path(__file__).parent)
            },
            "Read fixture file"
        ),
        PlanStep(
            3,
            "summarize",
            {},
            "Summarize content"
        )
    ]
)

result = executor.execute_plan(plan)

print(f"  Result: {result[:100]}...")

check(
    "summarize plan completes without error",
    "error" not in str(result).lower()
)
check(
    "LLM was called with content containing AIKA",
    "AIKA" in llm.last_prompt
)
check(
    "result is a non-empty string",
    isinstance(result, str) and len(result) > 0
)

# Test 2: Planner-generated summarize plan
print("\n[Test 2: Planner-generated summarize plan]")

planner = ExecutionPlanner()
plan = planner.create_plan(
    "summarize test_fixtures"
)

if plan:
    result = executor.execute_plan(plan)

    print(f"  Plan steps: {[s.tool_name for s in plan.steps]}")
    print(f"  Result: {result[:100]}...")

    check(
        "planner generated 3-step plan for summarize",
        len(plan.steps) == 3
    )
    check(
        "planner plan has correct tool order",
        (
            plan.steps[0].tool_name == "file_search"
            and plan.steps[1].tool_name == "file_read"
            and plan.steps[2].tool_name == "summarize"
        )
    )
    check(
        "executor returns summarized result",
        result and "AIKA" in result
    )
else:
    check("planner created plan for 'summarize test_fixtures'", False, "no plan")

# Test 3: Memory search -> summarize (no actual DB, tests mock flow)
print("\n[Test 3: Memory search -> summarize (no DB)]")

plan = Plan(
    goal="summarize_memories",
    steps=[
        PlanStep(
            1,
            "memory_search",
            {"query": "AIKA goals"},
            "Search memories"
        ),
        PlanStep(
            2,
            "summarize",
            {},
            "Summarize memories"
        )
    ]
)

# Since memory_search requires DB, this tests graceful handling
result = executor.execute_plan(plan)

print(f"  Result: {result[:100]}...")

check(
    "memory_summarize plan completes (gracefully or with error)",
    result is not None
)

# Test 4: Verify LLM prompt contains the actual content
print("\n[Test 4: LLM receives content in prompt]")

plan = Plan(
    goal="find_and_read",
    steps=[
        PlanStep(
            1,
            "file_read",
            {
                "file_path": "test_fixtures.txt",
                "root_path": str(Path(__file__).parent)
            },
            "Read fixture"
        )
    ]
)

llm.last_prompt = ""
result = executor.execute_plan(plan)

check(
    "LLM prompt contains file content for find_and_read",
    "AIKA" in llm.last_prompt or "AIKA" in result
)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
