import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from planner.execution_planner import ExecutionPlanner

passed = 0
failed = 0


def check(
    name,
    plan,
    expected_tools
):

    global passed, failed

    if plan is None:

        if expected_tools is None:
            print(f"  PASS: {name} (no plan as expected)")
            passed += 1
            return

        print(f"  FAIL: {name} - expected plan, got None")
        failed += 1
        return

    tools = [
        step.tool_name
        for step in plan.steps
    ]

    if tools == expected_tools:
        print(f"  PASS: {name} -> {tools}")
        passed += 1
    else:
        print(
            f"  FAIL: {name} - "
            f"expected {expected_tools}, got {tools}"
        )
        failed += 1


print("=== Stage 1: Test the Planner ===\n")

planner = ExecutionPlanner()

# Workflow 1: summarize -> file_search -> file_read -> summarize
check(
    "summarize my AIKA document",
    planner.create_plan("summarize my AIKA document"),
    ["file_search", "file_read", "summarize"]
)

# Workflow 2: analyze with file context
check(
    "analyze my project files",
    planner.create_plan("analyze my project files"),
    ["file_search", "file_read", "summarize"]
)

# Workflow 3: read and summarize (direct file)
check(
    "read and summarize notes.txt",
    planner.create_plan("read and summarize notes.txt"),
    ["file_read", "summarize"]
)

# Workflow 4: review with memory
check(
    "review my memories",
    planner.create_plan("review my memories"),
    ["memory_search", "summarize"]
)

# Workflow 5: analyze with explicit memory
check(
    "analyze my memories about AIKA",
    planner.create_plan("analyze my memories about AIKA"),
    ["memory_search", "summarize"]
)

# Workflow 6: find and read
check(
    "find and read AIKA architecture",
    planner.create_plan("find and read AIKA architecture"),
    ["file_search", "file_read"]
)

# Workflow 7: find file
check(
    "find my resume",
    planner.create_plan("find my resume"),
    ["file_search", "file_read"]
)

# Workflow 8: read file directly
check(
    "read my notes",
    planner.create_plan("read my notes"),
    ["file_read"]
)

# Workflow 9: no match
check(
    "hello",
    planner.create_plan("hello"),
    None
)

# Workflow 10: inspect
check(
    "inspect the system architecture",
    planner.create_plan("inspect the system architecture"),
    ["file_search", "file_read", "summarize"]
)

# Workflow 11: research
check(
    "research the AIKA codebase",
    planner.create_plan("research the AIKA codebase"),
    ["file_search", "file_read", "summarize"]
)

print()

# Verify step order is correct for a multi-step plan
plan = planner.create_plan(
    "summarize my AIKA document"
)

order_ok = (
    plan.steps[0].step_id == 1
    and plan.steps[0].tool_name == "file_search"
    and plan.steps[1].step_id == 2
    and plan.steps[1].tool_name == "file_read"
    and plan.steps[2].step_id == 3
    and plan.steps[2].tool_name == "summarize"
)

if order_ok:
    print("  PASS: Step IDs are sequential and tools are in correct order")
    passed += 1
else:
    print("  FAIL: Step order is incorrect")
    failed += 1

# Verify goal is set
if plan.goal == "summarize":
    print("  PASS: Goal is set correctly")
    passed += 1
else:
    print(f"  FAIL: Goal is '{plan.goal}', expected 'summarize'")
    failed += 1

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
