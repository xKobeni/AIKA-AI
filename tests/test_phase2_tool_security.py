import json
import os
from pathlib import Path
from unittest.mock import patch


def test_neighbor_prefix_path_is_not_inside_workspace(tmp_path):
    from tools.file_read_tool import FileReadTool

    root = tmp_path / "work"
    neighbor = tmp_path / "workspace"
    root.mkdir()
    neighbor.mkdir()
    (neighbor / "secret.txt").write_text("secret", encoding="utf-8")

    result = FileReadTool().execute(
        str(neighbor / "secret.txt"), root_path=str(root)
    )

    assert result["success"] is False
    assert "outside workspace" in result["error"]


def test_read_and_read_range_block_protected_files(tmp_path):
    from tools.file_read_range_tool import FileReadRangeTool
    from tools.file_read_tool import FileReadTool

    (tmp_path / ".env").write_text("TOKEN=private", encoding="utf-8")

    for tool in (FileReadTool(), FileReadRangeTool()):
        result = tool.execute(".env", root_path=str(tmp_path))
        assert result["success"] is False
        assert "protected" in result["error"]


def test_search_grep_and_folder_hide_protected_paths(tmp_path):
    from tools.file_grep_tool import FileGrepTool
    from tools.file_search_tool import FileSearchTool
    from tools.folder_tool import FolderTool

    (tmp_path / ".env").write_text("UNIQUE_SECRET=value", encoding="utf-8")
    (tmp_path / "visible.txt").write_text("safe", encoding="utf-8")

    search = FileSearchTool().execute(".env", root_path=str(tmp_path))
    grep = FileGrepTool().execute("UNIQUE_SECRET", root_path=str(tmp_path))
    with patch("tools.folder_tool.settings") as mock_settings:
        mock_settings.file_search_root_path = str(tmp_path)
        folder = FolderTool().execute(show_hidden=True)

    assert search["success"] is False
    assert search["file_paths"] == []
    assert grep["success"] is True and grep["matches"] == []
    assert all(".env" not in item for item in folder["files"])


def test_grep_does_not_follow_file_symlink_outside_workspace(tmp_path):
    from tools.file_grep_tool import FileGrepTool

    root = tmp_path / "workspace"
    root.mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("EXTERNAL_SECRET", encoding="utf-8")
    link = root / "linked.txt"
    try:
        os.symlink(outside, link)
    except (OSError, NotImplementedError):
        return

    result = FileGrepTool().execute("EXTERNAL_SECRET", root_path=str(root))
    assert result["success"] is True
    assert result["matches"] == []


def test_all_mutating_tools_reject_protected_paths(tmp_path):
    from tools.file_append_tool import FileAppendTool
    from tools.file_delete_tool import FileDeleteTool
    from tools.file_edit_tool import FileEditTool
    from tools.file_mkdir_tool import FileMkdirTool
    from tools.file_multi_edit_tool import FileMultiEditTool
    from tools.file_write_tool import FileWriteTool

    protected = tmp_path / ".env"
    protected.write_text("old", encoding="utf-8")

    calls = [
        FileWriteTool().execute(".env", "new", root_path=str(tmp_path)),
        FileAppendTool().execute(".env", "new", root_path=str(tmp_path)),
        FileEditTool().execute(".env", "old", "new", root_path=str(tmp_path)),
        FileDeleteTool().execute(".env", root_path=str(tmp_path)),
        FileMkdirTool().execute(".git", root_path=str(tmp_path)),
        FileMultiEditTool().execute(
            [{"file_path": ".env", "old_text": "old", "new_text": "new"}],
            root_path=str(tmp_path),
        ),
    ]

    assert all(result["success"] is False for result in calls)
    assert protected.read_text(encoding="utf-8") == "old"


def test_audit_log_redacts_sensitive_parameters(tmp_path):
    from tools.tool_manager import ToolManager

    log_path = tmp_path / "audit.log"
    manager = ToolManager()
    with patch("config.settings.settings") as mock_settings:
        mock_settings.audit_log_enabled = True
        mock_settings.audit_log_path = str(log_path)
        manager._audit_log(
            "example",
            {
                "password": "do-not-log",
                "content": "private body",
                "command": "curl -H 'Authorization: Bearer secret-token'",
            },
            {"success": True},
        )

    entry = json.loads(log_path.read_text(encoding="utf-8"))
    serialized = entry["parameters"]
    assert "do-not-log" not in serialized
    assert "private body" not in serialized
    assert "secret-token" not in serialized
    assert "[REDACTED]" in serialized


def test_tool_manager_contains_tool_exceptions_and_audits_failure(tmp_path):
    from tools.base_tool import BaseTool
    from tools.tool_manager import ToolManager

    class ExplodingTool(BaseTool):
        name = "explode"

        def execute(self, **kwargs):
            raise RuntimeError("sensitive internal detail")

    log_path = tmp_path / "audit.log"
    manager = ToolManager()
    manager.register_tool(ExplodingTool())
    with patch("config.settings.settings") as mock_settings:
        mock_settings.tool_call_max_params_length = 10_000
        mock_settings.tool_call_confirm_high_permission = False
        mock_settings.audit_log_enabled = True
        mock_settings.audit_log_path = str(log_path)
        result = manager.execute_tool("explode", token="private-token")

    assert result == {
        "success": False,
        "error": "Tool execution failed: RuntimeError",
    }
    log_content = log_path.read_text(encoding="utf-8")
    assert "private-token" not in log_content
    assert "sensitive internal detail" not in log_content
