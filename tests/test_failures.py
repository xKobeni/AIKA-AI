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
from tools.calculator_tool import CalculatorTool
from tools.file_search_tool import FileSearchTool
from tools.file_read_tool import FileReadTool
from brain.router import Router
from brain.decision_engine import DecisionEngine
from models.actions import Action

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
        return "[MOCK] Response"


class MockMemoryHandler:
    def store_memory(self, msg): return f"Stored: {msg}"
    def list_memories(self): return "(mock)"
    def search_memory(self, q): return f"Searching: {q}"
    def delete_memory(self, mid): return f"Deleted: {mid}"


class MockChatHandler:
    def chat(self, msg, intent=None, tool_name=None, agent_id=None): return f"[MOCK CHAT] You said: {msg}"


class MockToolHandler:
    def __init__(self):
        self.tm = ToolManager()
        self.tm.register_tool(CalculatorTool())
        self.tm.register_tool(FileSearchTool())
        self.tm.register_tool(FileReadTool())

    def handle(self, tr):
        try:
            r = self.tm.execute_tool(tr.tool_name, **tr.parameters)
            if isinstance(r, dict):
                if r.get("success"):
                    for v in r.values():
                        if isinstance(v, str) and v:
                            return v
                    return str(r)
                return r.get("error", "Tool failed")
            return str(r)
        except Exception as e:
            return f"Tool error: {e}"


class MockConversationRepo:
    def clear(self): return "cleared"


print("=== Stage 6: Failure Tests ===\n")

tm = ToolManager()
tm.register_tool(CalculatorTool())
tm.register_tool(FileSearchTool())
tm.register_tool(FileReadTool())

llm = MockLLM()
planner = ExecutionPlanner()
executor = PlanExecutor(tm, llm)

# Test 1: Nonexistent file search
print("[Test 1: File search — no matches]")

plan = Plan(
    goal="find_and_read",
    steps=[
        PlanStep(
            1,
            "file_search",
            {
                "query": "THIS_FILE_DOES_NOT_EXIST_XYZ_123",
                "root_path": str(Path(__file__).parent)
            },
            "Search for nonexistent file"
        ),
        PlanStep(
            2,
            "file_read",
            {
                "root_path": str(Path(__file__).parent)
            },
            "Read (should not happen)"
        )
    ]
)

try:
    result = executor.execute_plan(plan)
    has_traceback = "Traceback" in str(result)
    check(
        "nonexistent file search does not crash",
        not has_traceback,
        "got traceback in output"
    )
    check(
        "nonexistent file search handled gracefully",
        result is not None
    )
except Exception as e:
    check(
        "nonexistent file search does not raise exception",
        False,
        f"raised {type(e).__name__}: {e}"
    )

# Test 2: Empty file read
print("\n[Test 2: Empty file read]")

plan = Plan(
    goal="find_and_read",
    steps=[
        PlanStep(
            1,
            "file_read",
            {
                "file_path": "empty.txt",
                "root_path": str(Path(__file__).parent)
            },
            "Read empty file"
        )
    ]
)

try:
    result = executor.execute_plan(plan)
    check(
        "empty file read does not crash",
        True
    )
    check(
        "empty file read returns without error",
        "error" not in str(result).lower() or "no content" in str(result).lower()
    )
except Exception as e:
    check(
        "empty file read does not raise",
        False,
        f"raised {type(e).__name__}: {e}"
    )

# Test 3: Divide by zero
print("\n[Test 3: Calculator — divide by zero]")

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

try:
    result = executor.execute_plan(plan)
    check(
        "divide by zero does not crash",
        "Traceback" not in str(result)
    )
except Exception as e:
    check(
        "divide by zero does not raise",
        False,
        f"raised {type(e).__name__}: {e}"
    )

# Test 4: Planner returns None for unknown request
print("\n[Test 4: Planner — no matching workflow]")

plan = planner.create_plan("hello world")
check(
    "planner returns None for non-matching request",
    plan is None
)

# Test 5: Router handles None plan gracefully
print("\n[Test 5: Router — graceful message for no plan]")

class MockPlanner:
    def create_plan(self, msg):
        return None

class MockExecutor:
    def execute_plan(self, plan):
        return "executed"

router = Router(
    MockMemoryHandler(),
    MockChatHandler(),
    tool_handler=MockToolHandler(),
    conversation_repo=MockConversationRepo(),
    planner=MockPlanner(),
    executor=MockExecutor()
)

response = router.route(Action.PLAN_EXECUTION, "some request")
check(
    "router returns helpful message when planner returns None",
    "not sure" in str(response).lower()
)

# Test 6: DecisionEngine with no LLM returns CHAT for non-matching
print("\n[Test 6: DecisionEngine — no LLM fallback]")

de = DecisionEngine()
action = de.decide("tell me about dogs")
check(
    "decision engine returns CHAT when no LLM available",
    action == Action.CHAT,
    f"got {action}"
)

# Test 7: Missing tool in plan
print("\n[Test 7: Missing tool]")

plan = Plan(
    goal="test",
    steps=[
        PlanStep(
            1,
            "nonexistent_tool",
            {},
            "Missing tool"
        )
    ]
)

try:
    result = executor.execute_plan(plan)
    check(
        "missing tool handled gracefully",
        "error" in str(result).lower() or "not found" in str(result).lower()
    )
except Exception as e:
    check(
        "missing tool does not raise unhandled exception",
        False,
        f"raised {type(e).__name__}: {e}"
    )

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
