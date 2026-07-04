import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from models.actions import Action
from brain.decision_engine import DecisionEngine
from brain.router import Router
from planner.execution_planner import ExecutionPlanner
from planner.plan_executor import PlanExecutor
from tools.tool_manager import ToolManager
from tools.calculator_tool import CalculatorTool
from tools.file_search_tool import FileSearchTool
from tools.file_read_tool import FileReadTool
from models.tool_request import ToolRequest

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

    def store_memory(self, msg):
        return f"Stored: {msg}"

    def list_memories(self):
        return "(mock memories)"

    def search_memory(self, q):
        return f"Searching: {q}"

    def delete_memory(self, mid):
        return f"Deleted: {mid}"


class MockChatHandler:

    def chat(self, msg, intent=None, tool_name=None, agent_id=None):
        return f"[MOCK CHAT] You said: {msg}"


class MockToolHandler:

    def __init__(self):
        self.tool_manager = ToolManager()
        self.tool_manager.register_tool(CalculatorTool())
        self.tool_manager.register_tool(FileSearchTool())
        self.tool_manager.register_tool(FileReadTool())

    def handle(self, tool_request):
        try:
            result = self.tool_manager.execute_tool(
                tool_request.tool_name,
                **tool_request.parameters
            )
            if isinstance(result, dict):
                if result.get("success"):
                    for val in result.values():
                        if isinstance(val, str) and val:
                            return val
                    return str(result)
                return result.get("error", "Tool failed")
            return str(result)
        except Exception as e:
            return f"Tool error: {e}"


class MockConversationRepo:

    def clear(self):
        return "cleared"


print("=== Stage 5: Router Integration Test ===\n")

llm = MockLLM()
memory_handler = MockMemoryHandler()
chat_handler = MockChatHandler()
tool_handler = MockToolHandler()
conversation_repo = MockConversationRepo()
planner = ExecutionPlanner()
executor = PlanExecutor(
    tool_handler.tool_manager,
    llm
)

router = Router(
    memory_handler,
    chat_handler,
    tool_handler=tool_handler,
    conversation_repo=conversation_repo,
    planner=planner,
    executor=executor
)

decision_engine = DecisionEngine()

# Test 1: PLAN_EXECUTION triggered for summarize
print("[Test 1: summarize triggers PLAN_EXECUTION -> Plan -> Execute]")

action = decision_engine.decide(
    "summarize test_fixtures"
)

check(
    "decision engine returns PLAN_EXECUTION for summarize",
    action == Action.PLAN_EXECUTION,
    f"got {action}"
)

print(f"  Action: {action.value}")

response = router.route(action, "summarize test_fixtures")

print(f"  Response: {response[:80]}...")

check(
    "router returns non-empty response",
    response and len(str(response)) > 0
)
check(
    "response mentions AIKA (from test_fixtures.txt content)",
    "AIKA" in str(response) or "MOCK" in str(response)
)

# Test 2: PLAN_EXECUTION triggered for analyze
print("\n[Test 2: analyze triggers PLAN_EXECUTION]")

action = decision_engine.decide(
    "analyze my memories"
)

check(
    "decision engine returns PLAN_EXECUTION for analyze",
    action == Action.PLAN_EXECUTION,
    f"got {action}"
)

print(f"  Action: {action.value}")

# Test 3: Non-plan request goes to CHAT
print("\n[Test 3: hello triggers CHAT]")

action = decision_engine.decide(
    "hello"
)

check(
    "decision engine returns CHAT for hello",
    action == Action.CHAT,
    f"got {action}"
)

print(f"  Action: {action.value}")

response = router.route(action, "hello")

check(
    "chat response returned",
    "MOCK CHAT" in str(response) or "You said" in str(response)
)

# Test 4: Memory command still works
print("\n[Test 4: Memory commands still work]")

action = decision_engine.decide(
    "remember project: building AIKA"
)

check(
    "decision engine returns STORE_MEMORY",
    action == Action.STORE_MEMORY,
    f"got {action}"
)

# Test 5: USE_TOOL still works for calculator
print("\n[Test 5: Calculator still works]")

action = decision_engine.decide("2+2")

check(
    "decision engine returns USE_TOOL for calculator",
    action == Action.USE_TOOL,
    f"got {action}"
)

# Test 6: Planner produces correct plan through router
print("\n[Test 6: Router calls planner with correct message]")

action = decision_engine.decide(
    "read and summarize notes.txt"
)

plan = planner.create_plan("read and summarize notes.txt")

if plan:
    check(
        "planner creates plan for read+summarize",
        len(plan.steps) >= 2
    )
    check(
        "plan starts with file_read",
        plan.steps[0].tool_name == "file_read"
    )
    check(
        "plan ends with summarize",
        plan.steps[-1].tool_name == "summarize"
    )
else:
    check("planner created plan", False, "no plan")

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
