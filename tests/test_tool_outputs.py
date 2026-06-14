import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

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


def validate_tool_output(name, result, required_keys):
    if not isinstance(result, dict):
        return f"not a dict (got {type(result).__name__})"
    if "success" not in result:
        return "missing 'success' key"
    if result["success"] not in [True, False]:
        return f"'success' is not bool (got {type(result['success']).__name__})"
    for key in required_keys:
        if key not in result:
            return f"missing required key '{key}'"
    return None


print("=== Stage 7: Structured Output Validation ===\n")

tm = ToolManager()
tm.register_tool(CalculatorTool())
tm.register_tool(FileSearchTool())
tm.register_tool(FileReadTool())

# --- Calculator ---
print("[CalculatorTool]")

r = tm.execute_tool("calculator", expression="2+2")
err = validate_tool_output("calculator OK", r, ["result"])
check(
    "calculator returns dict with success and result",
    err is None,
    err
)
check(
    "calculator result equals 4",
    r["success"] and r["result"] == "4"
)

r = tm.execute_tool("calculator", expression="1/0")
err = validate_tool_output("calculator fail", r, ["error"])
check(
    "calculator error returns dict with success=False and error",
    err is None,
    err
)
check(
    "calculator error has success=False",
    r["success"] is False
)

# --- FileSearch ---
print("\n[FileSearchTool]")

r = tm.execute_tool(
    "file_search",
    query="test_fixtures",
    root_path=str(Path(__file__).parent)
)
err = validate_tool_output("file_search found", r, ["file_paths"])
check(
    "file_search returns dict with success and file_paths",
    err is None,
    err
)
check(
    "file_search found test_fixtures.txt",
    r["success"] and any(
        "test_fixtures" in p
        for p in r["file_paths"]
    )
)

r = tm.execute_tool(
    "file_search",
    query="NONEXISTENT_FILE_XYZ_123",
    root_path=str(Path(__file__).parent)
)
err = validate_tool_output("file_search not found", r, ["file_paths"])
check(
    "file_search not-found returns dict with success and file_paths",
    err is None,
    err
)
check(
    "file_search not-found has success=False",
    r["success"] is False
)
check(
    "file_search not-found has empty file_paths",
    r["file_paths"] == []
)

# --- FileRead ---
print("\n[FileReadTool]")

fixture_path = "test_fixtures.txt"

r = tm.execute_tool(
    "file_read",
    file_path=fixture_path,
    root_path=str(Path(__file__).parent)
)
err = validate_tool_output("file_read found", r, ["content"])
check(
    "file_read returns dict with success and content",
    err is None,
    err
)
check(
    "file_read has success=True",
    r["success"] is True
)
check(
    "file_read content is non-empty string",
    isinstance(r["content"], str) and len(r["content"]) > 0
)

r = tm.execute_tool(
    "file_read",
    file_path="nonexistent.txt",
    root_path=str(Path(__file__).parent)
)
err = validate_tool_output("file_read not found", r, ["error"])
check(
    "file_read not-found returns dict with success and error",
    err is None,
    err
)
check(
    "file_read not-found has success=False",
    r["success"] is False
)

# Verify all return types are dicts (never raw strings/lists)
all_tools_return_dicts = True

for r_text in [
    tm.execute_tool("calculator", expression="99+1"),
    tm.execute_tool("file_search", query="test", root_path="."),
    tm.execute_tool("file_read", file_path="requirements.txt",
                    root_path=str(Path(__file__).parent.parent))
]:
    if not isinstance(r_text, dict):
        all_tools_return_dicts = False
        break

check(
    "All tools consistently return dicts",
    all_tools_return_dicts
)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
