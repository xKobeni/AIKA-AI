import json
import os
from pathlib import Path
from unittest.mock import Mock, patch


FILESYSTEM_MUTATION_TOOL_NAMES = (
    "file_write",
    "file_append",
    "file_edit",
    "file_multi_edit",
    "file_mkdir",
    "file_delete",
)


def _manager_settings(mock_settings):
    mock_settings.tool_call_max_params_length = 10_000
    mock_settings.tool_call_confirm_high_permission = True
    mock_settings.audit_log_enabled = False


def test_all_filesystem_mutations_are_high_permission():
    from tools.file_append_tool import FileAppendTool
    from tools.file_delete_tool import FileDeleteTool
    from tools.file_edit_tool import FileEditTool
    from tools.file_mkdir_tool import FileMkdirTool
    from tools.file_multi_edit_tool import FileMultiEditTool
    from tools.file_write_tool import FileWriteTool
    from tools.tool_manager import ToolManager
    from tools.tool_permission import ToolPermission

    tools = (
        FileWriteTool(),
        FileAppendTool(),
        FileEditTool(),
        FileMultiEditTool(),
        FileMkdirTool(),
        FileDeleteTool(),
    )
    manager = ToolManager()

    for tool in tools:
        manager.register_tool(tool)

    assert {tool.name for tool in tools} == set(FILESYSTEM_MUTATION_TOOL_NAMES)
    assert all(tool.permission == ToolPermission.HIGH for tool in tools)
    assert all(
        manager.is_high_permission(tool_name)
        for tool_name in FILESYSTEM_MUTATION_TOOL_NAMES
    )


def test_manager_rejection_prevents_every_filesystem_mutation():
    from tools.tool_manager import ToolManager
    from tools.tool_permission import ToolPermission

    confirmation = Mock(return_value=False)
    manager = ToolManager(confirmation_handler=confirmation)
    registered = []

    for tool_name in FILESYSTEM_MUTATION_TOOL_NAMES:
        tool = Mock()
        tool.name = tool_name
        tool.permission = ToolPermission.MEDIUM
        tool.execute.return_value = {"success": True}
        manager.register_tool(tool)
        registered.append(tool)

    with patch("config.settings.settings") as mock_settings:
        _manager_settings(mock_settings)
        results = [
            manager.execute_tool(tool_name, target="example")
            for tool_name in FILESYSTEM_MUTATION_TOOL_NAMES
        ]

    assert all(result["success"] is False for result in results)
    assert all("cancelled" in result["error"].lower() for result in results)
    assert confirmation.call_count == len(FILESYSTEM_MUTATION_TOOL_NAMES)
    assert all(tool.execute.call_count == 0 for tool in registered)


def test_manager_approval_executes_filesystem_mutation_exactly_once():
    from tools.tool_manager import ToolManager
    from tools.tool_permission import ToolPermission

    tool = Mock()
    tool.name = "file_append"
    tool.permission = ToolPermission.MEDIUM
    tool.execute.return_value = {"success": True}
    confirmation = Mock(return_value=True)
    manager = ToolManager(confirmation_handler=confirmation)
    manager.register_tool(tool)

    with patch("config.settings.settings") as mock_settings:
        _manager_settings(mock_settings)
        result = manager.execute_tool(
            "file_append", file_path="example.txt", content="hello"
        )

    assert result == {"success": True}
    confirmation.assert_called_once()
    tool.execute.assert_called_once_with(
        file_path="example.txt", content="hello"
    )


def test_rejected_append_cannot_create_a_new_file(tmp_path):
    from tools.file_append_tool import FileAppendTool
    from tools.tool_manager import ToolManager

    target = tmp_path / "new.txt"
    confirmation = Mock(return_value=False)
    manager = ToolManager(confirmation_handler=confirmation)
    manager.register_tool(FileAppendTool())

    with patch("config.settings.settings") as mock_settings:
        _manager_settings(mock_settings)
        result = manager.execute_tool(
            "file_append",
            file_path=target.name,
            content="must not be written",
            root_path=str(tmp_path),
        )

    assert result["success"] is False
    assert not target.exists()
    confirmation.assert_called_once()


def test_disabled_write_setting_blocks_every_write_operation(
    tmp_path, monkeypatch
):
    from config.settings import settings
    from tools.file_append_tool import FileAppendTool
    from tools.file_edit_tool import FileEditTool
    from tools.file_mkdir_tool import FileMkdirTool
    from tools.file_multi_edit_tool import FileMultiEditTool
    from tools.file_write_tool import FileWriteTool

    existing = tmp_path / "existing.txt"
    existing.write_text("old", encoding="utf-8")
    monkeypatch.setattr(settings, "file_write_enabled", False)

    results = (
        FileWriteTool().execute("new.txt", "new", root_path=str(tmp_path)),
        FileAppendTool().execute(
            "existing.txt", "new", root_path=str(tmp_path)
        ),
        FileEditTool().execute(
            "existing.txt", "old", "new", root_path=str(tmp_path)
        ),
        FileMultiEditTool().execute(
            [{
                "file_path": "existing.txt",
                "old_text": "old",
                "new_text": "new",
            }],
            root_path=str(tmp_path),
        ),
        FileMkdirTool().execute("new-dir", root_path=str(tmp_path)),
    )

    assert all(result["success"] is False for result in results)
    assert all(result["error"] == "File write is disabled" for result in results)
    assert existing.read_text(encoding="utf-8") == "old"
    assert not (tmp_path / "new.txt").exists()
    assert not (tmp_path / "new-dir").exists()


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


def test_desktop_alias_remains_contained_to_resolved_known_folder(tmp_path):
    from tools.path_security import resolve_user_scoped_path

    with patch(
        "tools.path_security.resolve_known_user_folder",
        return_value=tmp_path,
    ):
        root, target = resolve_user_scoped_path(".", "desktop://blank.txt")
        _, traversal = resolve_user_scoped_path(".", "desktop://../secret.txt")

    assert root == tmp_path.resolve()
    assert target == (tmp_path / "blank.txt").resolve()
    assert traversal is None


def test_file_write_desktop_alias_creates_only_inside_known_folder(tmp_path):
    from tools.file_write_tool import FileWriteTool

    with patch(
        "tools.path_security.resolve_known_user_folder",
        return_value=tmp_path,
    ):
        result = FileWriteTool().execute("desktop://blank.txt", "")
        existing = FileWriteTool().execute(
            "desktop://blank.txt", "replacement", fail_if_exists=True
        )

    assert result["success"] is True
    assert result["bytes_written"] == 0
    assert (tmp_path / "blank.txt").read_text(encoding="utf-8") == ""

    assert existing["success"] is False
    assert "already exists" in existing["error"]
    assert (tmp_path / "blank.txt").read_text(encoding="utf-8") == ""


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
