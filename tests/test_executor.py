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
from tools.tool_manager import ToolManager
from tools.calculator_tool import CalculatorTool
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

    def generate(self, prompt):
        return "[MOCK] Executed summarize step"


print("=== Stage 2: Test the Executor ===\n")

tm = ToolManager()
tm.register_tool(CalculatorTool())
tm.register_tool(FileSearchTool())
tm.register_tool(FileReadTool())

llm = MockLLM()
executor = PlanExecutor(tm, llm)

# Test 1: Calculator
print("[Test 1: Calculator]")

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "calculator",
            {"expression": "2+2"},
            "Calculate 2+2"
        )
    ]
)

result = executor.execute_plan(plan)
check(
    "calculator returns correct result in response",
    "4" in str(result)
)

# Test 2: File search
print("\n[Test 2: File Search]")

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "file_search",
            {"query": "test_fixtures"},
            "Search for test fixture file"
        )
    ]
)

result = executor.execute_plan(plan)
check(
    "file_search completes without error",
    "error" not in str(result).lower()
)
check(
    "file_search returns result",
    result is not None and len(str(result)) > 0
)

# Test 3: File read with explicit path
print("\n[Test 3: File Read (explicit path)]")

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "file_read",
            {
                "file_path": "test_fixtures.txt",
                "root_path": str(Path(__file__).parent)
            },
            "Read fixture file"
        )
    ]
)

result = executor.execute_plan(plan)
check(
    "file_read completes without error",
    "error" not in str(result).lower()
)
check(
    "file_read returns file content",
    "AIKA" in str(result)
)

# Test 4: Multi-step without LLM dependency (find + read)
print("\n[Test 4: Multi-step find + read]")

plan = Plan(
    goal="find_and_read",
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
            "Read the found file"
        )
    ]
)

result = executor.execute_plan(plan)
check(
    "multi-step find+read completes without error",
    "error" not in str(result).lower()
)
check(
    "multi-step find+read returns result",
    result is not None and len(str(result)) > 0
)

# Test 5: Error handling (nonexistent step)
print("\n[Test 5: Error handling]")

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "calculator",
            {"expression": "1/0"},
            "Divide by zero"
        )
    ]
)

result = executor.execute_plan(plan)
check(
    "divide by zero handled gracefully",
    "error" not in str(type(result)).lower()
)

# Test 6: No content to summarize
print("\n[Test 6: Summarize with no content]")

plan = Plan(
    goal="summarize",
    steps=[
        PlanStep(
            1,
            "summarize",
            {},
            "Summarize (no prior context)"
        )
    ]
)

result = executor.execute_plan(plan)
check(
    "summarize with no content returns message",
    "No content" in str(result) or "no content" in str(result)
)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
