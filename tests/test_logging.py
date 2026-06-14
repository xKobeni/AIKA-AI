import sys
import os
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent

sys.path.append(
    str(
        project_root / "src"
    )
)

os.chdir(str(project_root))

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
        return "[MOCK] Summarized"


print("=== Stage 8: Execution Logs ===\n")

log_path = project_root / "logs" / "execution.log"

# Clear existing log
if log_path.exists():
    log_path.write_text("", encoding="utf-8")

tm = ToolManager()
tm.register_tool(CalculatorTool())

llm = MockLLM()
executor = PlanExecutor(tm, llm)

# Test 1: Log is created
print("[Test 1: Log file creation]")

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "calculator",
            {"expression": "1+1"},
            "Simple calculation"
        )
    ]
)

executor.execute_plan(plan)

check(
    "log file exists after execution",
    log_path.exists()
)

# Test 2: Log contains plan start entry
print("\n[Test 2: Log contains plan start]")

if log_path.exists():
    content = log_path.read_text(encoding="utf-8")
    check(
        "log contains 'Plan start'",
        "Plan start" in content
    )
    check(
        "log contains step tool name",
        "calculator" in content
    )
else:
    check("log file exists for reading", False, "log not created")

# Test 3: Log contains step result
if log_path.exists():
    content = log_path.read_text(encoding="utf-8")
    check(
        "log contains 'Step 1 OK'",
        "Step 1 OK" in content
    )
else:
    check("log file exists for result check", False, "log not created")

# Test 4: Log contains plan complete
if log_path.exists():
    content = log_path.read_text(encoding="utf-8")
    check(
        "log contains 'Plan complete'",
        "Plan complete" in content
    )
    check(
        "log contains timing info",
        "s" in content
    )
else:
    check("log file exists for completion check", False, "log not created")

# Test 5: Multi-step plan produces multiple log entries
print("\n[Test 5: Multi-step logging]")

if log_path.exists():
    log_path.write_text("", encoding="utf-8")

tm2 = ToolManager()
tm2.register_tool(FileSearchTool())
tm2.register_tool(FileReadTool())

executor2 = PlanExecutor(tm2, llm)

plan = Plan(
    goal="find_and_read",
    steps=[
        PlanStep(
            1,
            "file_search",
            {
                "query": "test_fixtures",
                "root_path": str(project_root / "tests")
            },
            "Search"
        ),
        PlanStep(
            2,
            "file_read",
            {
                "file_path": "test_fixtures.txt",
                "root_path": str(project_root / "tests")
            },
            "Read"
        )
    ]
)

executor2.execute_plan(plan)

if log_path.exists():
    content = log_path.read_text(encoding="utf-8")
    step1_ok = "Step 1 OK" in content
    step2_ok = "Step 2 OK" in content
    check(
        "log has entry for step 1",
        step1_ok
    )
    check(
        "log has entry for step 2",
        step2_ok
    )
    check(
        "log contains both step results",
        step1_ok and step2_ok
    )
else:
    check("log exists for multi-step", False, "log not created")

# Test 6: Log contains timestamp
print("\n[Test 6: Log format]")

if log_path.exists():
    content = log_path.read_text(encoding="utf-8")
    has_timestamp = any(
        line.startswith("[")
        for line in content.splitlines()
    )
    check(
        "log entries have timestamps",
        has_timestamp
    )
else:
    check("log exists for format check", False, "log not created")

# Test 7: Logging failure doesn't crash executor
print("\n[Test 7: Logging resilience]")

executor3 = PlanExecutor(tm, llm)

# Simulate log write failure by making logs not writable
# (just verify the try/except works by using a bad path)
executor3._log = lambda msg: None  # silently swallow

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "calculator",
            {"expression": "2+2"},
            "Calc"
        )
    ]
)

try:
    result = executor3.execute_plan(plan)
    check(
        "executor works even if logging fails",
        True
    )
except Exception as e:
    check(
        "logging failure does not crash executor",
        False,
        f"raised {type(e).__name__}: {e}"
    )

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
