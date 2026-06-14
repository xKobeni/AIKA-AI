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

    def generate(self, prompt):
        return "[MOCK] Summarized content"


print("=== Stage 3: Test Context Passing ===\n")

tm = ToolManager()
tm.register_tool(FileSearchTool())
tm.register_tool(FileReadTool())

llm = MockLLM()
executor = PlanExecutor(tm, llm)

# Test 1: Manual plan with context injection
print("[Test 1: Manual plan - file_search -> file_read]")

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
            "Search for fixture"
        ),
        PlanStep(
            2,
            "file_read",
            {
                "root_path": str(Path(__file__).parent)
            },
            "Read found file"
        )
    ]
)

# Monkey-patch to inspect context
context_data = {}

original_store = executor._store_result


def tracking_store(tool_name, result, context):
    original_store(tool_name, result, context)
    context_data.update(context.data)


executor._store_result = tracking_store

result = executor.execute_plan(plan)

print(f"\n  Context data after execution:")
for key, value in context_data.items():
    val_str = (
        str(value)[:80]
        if isinstance(value, str)
        else str(value)[:80]
    )
    print(f"    {key}: {val_str}")

check(
    "context has file_paths from file_search",
    "file_paths" in context_data
)
check(
    "context has file_content from file_read",
    "file_content" in context_data
)
check(
    "file_paths is a list",
    isinstance(context_data.get("file_paths"), list)
)
check(
    "file_paths contains test_fixtures path",
    any(
        "test_fixtures" in p
        for p in context_data.get("file_paths", [])
    )
)
check(
    "file_content contains AIKA",
    "AIKA" in context_data.get("file_content", "")
)

# Test 2: Planner-generated plan with context passing
print("\n[Test 2: Planner-generated plan]")

planner = ExecutionPlanner()
plan = planner.create_plan(
    "read and summarize test_fixtures"
)

if plan:
    context_data2 = {}
    original_store2 = executor._store_result

    def tracking_store2(tool_name, result, context):
        original_store2(tool_name, result, context)
        context_data2.update(context.data)

    executor._store_result = tracking_store2

    executor._inject_context_params = lambda tn, p, c: PlanExecutor._inject_context_params(
        executor, tn, p, c
    )

    result = executor.execute_plan(plan)

    print(f"\n  Planner plan steps:")
    for step in plan.steps:
        print(f"    Step {step.step_id}: {step.tool_name}")

    check(
        "context has file_content after planner plan",
        "file_content" in context_data2
    )
else:
    check("planner created plan", False, "no plan generated")
    context_data2 = {}

# Test 3: Verify file_read receives correct path from context
print("\n[Test 3: Path injection from context]")

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
            "Search"
        ),
        PlanStep(
            2,
            "file_read",
            {
                "root_path": str(Path(__file__).parent)
            },
            "Read"
        )
    ]
)

received_params = []

original_execute = tm.execute_tool


def tracking_execute(tool_name, **kwargs):
    if tool_name == "file_read":
        received_params.append(dict(kwargs))
    return original_execute(tool_name, **kwargs)


tm.execute_tool = tracking_execute

executor._store_result = original_store
executor.execute_plan(plan)

if received_params:
    check(
        "file_read received file_path parameter",
        "file_path" in received_params[0]
    )
    check(
        "file_path contains test_fixtures",
        "test_fixtures" in received_params[0].get("file_path", "")
    )
else:
    check("file_read was called", False, "file_read was never invoked")

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
