import sys
import os
import tempfile
import shutil
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from unittest.mock import patch, MagicMock
from tools.file_write_tool import FileWriteTool
from brain.decision_engine import DecisionEngine
from brain.router import Router
from models.actions import Action
from config.settings import settings


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


print("=== Test FileWriteTool ===\n")

tmp_dir = tempfile.mkdtemp()
try:

    tool = FileWriteTool()

    check(
        "tool name is file_write",
        tool.name == "file_write"
    )

    check(
        "tool category is FILE",
        tool.category.value == "file"
    )

    check(
        "tool permission is HIGH",
        tool.permission.value == "high"
    )

    result = tool.execute(
        "test.txt",
        "Hello, World!",
        root_path=tmp_dir
    )

    check(
        "write returns success",
        result["success"] is True
    )

    check(
        "write returns file_path",
        "file_path" in result
    )

    check(
        "write returns bytes_written",
        result["bytes_written"] > 0
    )

    written_file = Path(tmp_dir) / "test.txt"
    check(
        "file exists after write",
        written_file.exists()
    )

    check(
        "file content is correct",
        written_file.read_text() == "Hello, World!"
    )

    result2 = tool.execute(
        "test.txt",
        "Updated content",
        root_path=tmp_dir
    )

    check(
        "overwrite returns success",
        result2["success"] is True
    )

    check(
        "file content is updated",
        written_file.read_text() == "Updated content"
    )

    result3 = tool.execute(
        "subdir/nested/test.txt",
        "Nested file",
        root_path=tmp_dir
    )

    check(
        "creates nested directories",
        result3["success"] is True
    )

    nested_file = Path(tmp_dir) / "subdir" / "nested" / "test.txt"
    check(
        "nested file exists",
        nested_file.exists()
    )

    result4 = tool.execute(
        "../../etc/passwd",
        "malicious",
        root_path=tmp_dir
    )

    check(
        "blocks path traversal",
        result4["success"] is False
    )

    check(
        "path traversal error message",
        "Access denied" in result4["error"]
    )

    with patch("tools.file_write_tool.settings") as mock_settings:
        mock_settings.file_write_enabled = False
        mock_settings.file_search_root_path = tmp_dir
        mock_settings.file_read_encoding = "utf-8"

        tool_disabled = FileWriteTool()
        result5 = tool_disabled.execute(
            "test.txt",
            "content",
            root_path=tmp_dir
        )

        check(
            "returns error when disabled",
            result5["success"] is False
        )

        check(
            "disabled error message",
            "disabled" in result5["error"].lower()
        )

finally:
    shutil.rmtree(tmp_dir)


print("\n=== Test Decision Engine Prefix Rules ===\n")

engine = DecisionEngine()

check(
    "create triggers USE_TOOL",
    engine.decide("create a todo list") == Action.USE_TOOL
)

check(
    "write triggers USE_TOOL",
    engine.decide("write a shopping list") == Action.USE_TOOL
)

check(
    "make triggers USE_TOOL",
    engine.decide("make a note") == Action.USE_TOOL
)

check(
    "save triggers USE_TOOL",
    engine.decide("save my work") == Action.USE_TOOL
)

check(
    "save as triggers USE_TOOL",
    engine.decide("save as todo.html") == Action.USE_TOOL
)

check(
    "find still triggers USE_TOOL",
    engine.decide("find todo.txt") == Action.USE_TOOL
)

check(
    "read still triggers USE_TOOL",
    engine.decide("read todo.txt") == Action.USE_TOOL
)

check(
    "hello still triggers CHAT",
    engine.decide("hello") == Action.CHAT
)


print("\n=== Test Router File Write Dispatch ===\n")

mock_memory = MagicMock()
mock_chat = MagicMock()
mock_tool = MagicMock()
mock_conversation = MagicMock()
mock_planner = MagicMock()
mock_executor = MagicMock()
mock_intent = MagicMock()
mock_config = MagicMock()

mock_tool.handle.return_value = {
    "success": True,
    "file_path": "test.txt",
    "bytes_written": 12
}

router = Router(
    memory_handler=mock_memory,
    chat_handler=mock_chat,
    tool_handler=mock_tool,
    conversation_repo=mock_conversation,
    planner=mock_planner,
    executor=mock_executor,
    intent_classifier=mock_intent,
    config_handler=mock_config
)

router.route(Action.USE_TOOL, "create a todo list")

check(
    "tool_handler was called",
    mock_tool.handle.called
)

call_args = mock_tool.handle.call_args[0][0]
check(
    "tool name is file_write",
    call_args.tool_name == "file_write"
)

check(
    "parameters include file_path",
        "file_path" in call_args.parameters
)

check(
    "parameters include content",
    "content" in call_args.parameters
)

mock_tool.reset_mock()

router.route(Action.USE_TOOL, "write shopping list to grocery.html")

call_args2 = mock_tool.handle.call_args[0][0]
check(
    "explicit filename used",
    call_args2.parameters["file_path"] == "grocery.html"
)


print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
