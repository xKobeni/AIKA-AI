import sys
import tempfile
import shutil
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from unittest.mock import patch
from tools.file_delete_tool import FileDeleteTool
from tools.file_append_tool import FileAppendTool
from tools.file_edit_tool import FileEditTool
from tools.file_grep_tool import FileGrepTool
from tools.file_mkdir_tool import FileMkdirTool
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


print("=== Test FileDeleteTool ===\n")

tmp_dir = tempfile.mkdtemp()
try:

    test_file = Path(tmp_dir) / "delete_me.txt"
    test_file.write_text("hello")

    tool = FileDeleteTool()

    check(
        "tool name is file_delete",
        tool.name == "file_delete"
    )

    result = tool.execute("delete_me.txt", root_path=tmp_dir)

    check(
        "delete returns success",
        result["success"] is True
    )

    check(
        "file is deleted",
        not test_file.exists()
    )

    test_file2 = Path(tmp_dir) / "delete_me2.txt"
    test_file2.write_text("hello")

    result2 = tool.execute("nonexistent.txt", root_path=tmp_dir)

    check(
        "delete nonexistent returns error",
        result2["success"] is False
    )

    sub_dir = Path(tmp_dir) / "subdir"
    sub_dir.mkdir()
    (sub_dir / "file.txt").write_text("content")

    result3 = tool.execute("subdir", root_path=tmp_dir)

    check(
        "delete non-empty dir without recursive fails",
        result3["success"] is False
    )

    result4 = tool.execute("subdir", recursive=True, root_path=tmp_dir)

    check(
        "delete with recursive succeeds",
        result4["success"] is True
    )

    result5 = tool.execute("../../etc/passwd", root_path=tmp_dir)

    check(
        "blocks path traversal",
        result5["success"] is False
    )

    with patch("tools.file_delete_tool.settings") as mock_settings:
        mock_settings.file_delete_enabled = False
        mock_settings.file_search_root_path = tmp_dir

        tool_disabled = FileDeleteTool()
        result6 = tool_disabled.execute("delete_me2.txt", root_path=tmp_dir)

        check(
            "returns error when disabled",
            result6["success"] is False
        )

finally:
    shutil.rmtree(tmp_dir)


print("\n=== Test FileAppendTool ===\n")

tmp_dir = tempfile.mkdtemp()
try:

    tool = FileAppendTool()

    check(
        "tool name is file_append",
        tool.name == "file_append"
    )

    result = tool.execute(
        "test.txt",
        "Hello, World!",
        root_path=tmp_dir
    )

    check(
        "append creates new file",
        result["success"] is True
    )

    check(
        "file content is correct",
        (Path(tmp_dir) / "test.txt").read_text() == "Hello, World!"
    )

    result2 = tool.execute(
        "test.txt",
        "\nGoodbye!",
        root_path=tmp_dir
    )

    check(
        "append adds to existing file",
        result2["success"] is True
    )

    check(
        "file content is appended",
        (Path(tmp_dir) / "test.txt").read_text() == "Hello, World!\nGoodbye!"
    )

    result3 = tool.execute(
        "../../etc/passwd",
        "malicious",
        root_path=tmp_dir
    )

    check(
        "blocks path traversal",
        result3["success"] is False
    )

finally:
    shutil.rmtree(tmp_dir)


print("\n=== Test FileEditTool ===\n")

tmp_dir = tempfile.mkdtemp()
try:

    test_file = Path(tmp_dir) / "edit_me.txt"
    test_file.write_text("Hello, World! Hello, Universe!")

    tool = FileEditTool()

    check(
        "tool name is file_edit",
        tool.name == "file_edit"
    )

    result = tool.execute(
        "edit_me.txt",
        "Hello",
        "Hi",
        root_path=tmp_dir
    )

    check(
        "edit returns success",
        result["success"] is True
    )

    check(
        "replacements_made is 1",
        result["replacements_made"] == 1
    )

    check(
        "file content is updated",
        test_file.read_text() == "Hi, World! Hello, Universe!"
    )

    result2 = tool.execute(
        "edit_me.txt",
        "Hello",
        "Hi",
        replace_all=True,
        root_path=tmp_dir
    )

    check(
        "replace_all works",
        result2["replacements_made"] == 1
    )

    check(
        "all occurrences replaced",
        test_file.read_text() == "Hi, World! Hi, Universe!"
    )

    result3 = tool.execute(
        "edit_me.txt",
        "Nonexistent",
        "text",
        root_path=tmp_dir
    )

    check(
        "edit nonexistent text returns error",
        result3["success"] is False
    )

    result4 = tool.execute(
        "../../etc/passwd",
        "old",
        "new",
        root_path=tmp_dir
    )

    check(
        "blocks path traversal",
        result4["success"] is False
    )

finally:
    shutil.rmtree(tmp_dir)


print("\n=== Test FileGrepTool ===\n")

tmp_dir = tempfile.mkdtemp()
try:

    (Path(tmp_dir) / "file1.txt").write_text("Hello World\nGoodbye World")
    (Path(tmp_dir) / "file2.txt").write_text("Hello Python\nGoodbye Python")

    tool = FileGrepTool()

    check(
        "tool name is file_grep",
        tool.name == "file_grep"
    )

    result = tool.execute("Hello", root_path=tmp_dir)

    check(
        "grep returns success",
        result["success"] is True
    )

    check(
        "grep finds matches",
        len(result["matches"]) > 0
    )

    check(
        "match has file field",
        "file" in result["matches"][0]
    )

    check(
        "match has line_number field",
        "line_number" in result["matches"][0]
    )

    check(
        "match has line field",
        "line" in result["matches"][0]
    )

    result2 = tool.execute("NonexistentText12345", root_path=tmp_dir)

    check(
        "grep no matches returns empty",
        result2["success"] is True and len(result2["matches"]) == 0
    )

    result3 = tool.execute("test", path="../../etc", root_path=tmp_dir)

    check(
        "blocks path traversal",
        result3["success"] is False
    )

finally:
    shutil.rmtree(tmp_dir)


print("\n=== Test FileMkdirTool ===\n")

tmp_dir = tempfile.mkdtemp()
try:

    tool = FileMkdirTool()

    check(
        "tool name is file_mkdir",
        tool.name == "file_mkdir"
    )

    result = tool.execute("newdir", root_path=tmp_dir)

    check(
        "mkdir returns success",
        result["success"] is True
    )

    check(
        "directory is created",
        (Path(tmp_dir) / "newdir").exists()
    )

    check(
        "directory is a directory",
        (Path(tmp_dir) / "newdir").is_dir()
    )

    result2 = tool.execute("newdir", root_path=tmp_dir)

    check(
        "mkdir existing dir returns error",
        result2["success"] is False
    )

    result3 = tool.execute("parent/child/grandchild", root_path=tmp_dir)

    check(
        "mkdir with parents works",
        result3["success"] is True
    )

    check(
        "nested directory is created",
        (Path(tmp_dir) / "parent" / "child" / "grandchild").exists()
    )

    result4 = tool.execute("../../evil", root_path=tmp_dir)

    check(
        "blocks path traversal",
        result4["success"] is False
    )

finally:
    shutil.rmtree(tmp_dir)


print("\n=== Test Decision Engine Prefix Rules ===\n")

engine = DecisionEngine()

check(
    "delete triggers USE_TOOL",
    engine.decide("delete file.txt") == Action.USE_TOOL
)

check(
    "remove triggers USE_TOOL",
    engine.decide("remove file.txt") == Action.USE_TOOL
)

check(
    "append triggers USE_TOOL",
    engine.decide("append text to file.txt") == Action.USE_TOOL
)

check(
    "add to triggers USE_TOOL",
    engine.decide("add to file.txt") == Action.USE_TOOL
)

check(
    "edit triggers USE_TOOL",
    engine.decide("edit file.txt") == Action.USE_TOOL
)

check(
    "replace triggers USE_TOOL",
    engine.decide("replace old with new") == Action.USE_TOOL
)

check(
    "grep triggers USE_TOOL",
    engine.decide("grep pattern") == Action.USE_TOOL
)

check(
    "search in triggers USE_TOOL",
    engine.decide("search in file.txt") == Action.USE_TOOL
)

check(
    "find in triggers USE_TOOL",
    engine.decide("find in directory") == Action.USE_TOOL
)

check(
    "mkdir triggers USE_TOOL",
    engine.decide("mkdir newdir") == Action.USE_TOOL
)

check(
    "create folder triggers USE_TOOL",
    engine.decide("create folder newdir") == Action.USE_TOOL
)

check(
    "create directory triggers USE_TOOL",
    engine.decide("create directory newdir") == Action.USE_TOOL
)


print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
