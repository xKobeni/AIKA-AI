import json
import os
import tempfile
import pytest
from unittest.mock import patch, MagicMock


class TestDangerPhrases:

    def test_danger_phrases_exist(self):
        from brain.common import DANGER_PHRASES
        assert isinstance(DANGER_PHRASES, list)
        assert len(DANGER_PHRASES) > 0

    def test_danger_phrases_contain_key_words(self):
        from brain.common import DANGER_PHRASES
        assert "deleted" in DANGER_PHRASES
        assert "removed" in DANGER_PHRASES
        assert "overwritten" in DANGER_PHRASES


class TestToolManagerConfirmation:

    def test_high_permission_tool_requires_confirmation(self):
        from tools.tool_manager import ToolManager
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(ShellTool())
        assert tm.is_high_permission("shell") is True

    def test_low_permission_tool_not_high(self):
        from tools.tool_manager import ToolManager
        from tools.calculator_tool import CalculatorTool
        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        assert tm.is_high_permission("calculator") is False

    def test_check_confirmation_returns_true_when_disabled(self):
        from tools.tool_manager import ToolManager
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(ShellTool())
        with patch("config.settings.settings") as mock_settings:
            mock_settings.tool_call_confirm_high_permission = False
            result = tm._check_confirmation("shell", {"command": "dir"})
            assert result is True

    def test_check_confirmation_returns_true_for_low_permission(self):
        from tools.tool_manager import ToolManager
        from tools.calculator_tool import CalculatorTool
        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        with patch("config.settings.settings") as mock_settings:
            mock_settings.tool_call_confirm_high_permission = True
            result = tm._check_confirmation("calculator", {"expression": "1+1"})
            assert result is True

    def test_check_confirmation_prompts_user(self):
        from tools.tool_manager import ToolManager
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(ShellTool())
        with patch("config.settings.settings") as mock_settings:
            mock_settings.tool_call_confirm_high_permission = True
            with patch("builtins.input", return_value="y"):
                result = tm._check_confirmation("shell", {"command": "dir"})
                assert result is True

    def test_check_confirmation_rejects_user(self):
        from tools.tool_manager import ToolManager
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(ShellTool())
        with patch("config.settings.settings") as mock_settings:
            mock_settings.tool_call_confirm_high_permission = True
            with patch("builtins.input", return_value="n"):
                result = tm._check_confirmation("shell", {"command": "dir"})
                assert result is False


class TestToolManagerAuditLog:

    def test_audit_log_creates_file(self):
        from tools.tool_manager import ToolManager
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(ShellTool())

        with tempfile.NamedTemporaryFile(mode="w", suffix=".log", delete=False) as f:
            log_path = f.name

        try:
            with patch("config.settings.settings") as mock_settings:
                mock_settings.audit_log_enabled = True
                mock_settings.audit_log_path = log_path

                tm._audit_log("shell", {"command": "dir"}, {"success": True}, agent_id="test_agent")

            with open(log_path, "r") as f:
                lines = f.readlines()
                assert len(lines) == 1
                entry = json.loads(lines[0])
                assert entry["tool"] == "shell"
                assert entry["success"] is True
                assert entry["agent_id"] == "test_agent"
        finally:
            os.unlink(log_path)

    def test_audit_log_disabled_does_nothing(self):
        from tools.tool_manager import ToolManager
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(ShellTool())
        test_path = tempfile.mktemp(suffix=".log")
        with patch("config.settings.settings") as mock_settings:
            mock_settings.audit_log_enabled = False
            tm._audit_log("shell", {"command": "dir"}, {"success": True})
        assert not os.path.exists(test_path)


class TestProtectedPaths:

    def test_file_delete_protected_path(self):
        from tools.file_delete_tool import FileDeleteTool
        tool = FileDeleteTool()
        assert tool._is_protected_path(".env") is True
        assert tool._is_protected_path(".git/config") is True
        assert tool._is_protected_path("src/main.py") is False

    def test_file_write_protected_path(self):
        from tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        assert tool._is_protected_path("secret.key") is True
        assert tool._is_protected_path(".env") is True
        assert tool._is_protected_path("src/main.py") is False

    def test_file_write_rejects_protected_path(self):
        from tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        with patch("tools.file_write_tool.settings") as mock_settings:
            mock_settings.file_write_enabled = True
            mock_settings.file_search_root_path = "."
            result = tool.execute(".env", content="test")
            assert result["success"] is False
            assert "protected" in result["error"].lower()

    def test_file_write_rejects_large_content(self):
        from tools.file_write_tool import FileWriteTool
        tool = FileWriteTool()
        with patch("tools.file_write_tool.settings") as mock_settings:
            mock_settings.file_write_enabled = True
            mock_settings.file_search_root_path = "."
            large_content = "x" * 1_000_001
            result = tool.execute("test.txt", content=large_content)
            assert result["success"] is False
            assert "too large" in result["error"].lower()


class TestSettingsSafety:

    def test_safety_settings_exist(self):
        from config.settings import Settings
        with patch.dict("os.environ", {}, clear=False):
            s = Settings()
            assert hasattr(s, "tool_call_confirm_high_permission")
            assert hasattr(s, "audit_log_enabled")
            assert hasattr(s, "audit_log_path")
            assert hasattr(s, "protected_paths")

    def test_protected_paths_is_list(self):
        from config.settings import Settings
        with patch.dict("os.environ", {}, clear=False):
            s = Settings()
            assert isinstance(s.protected_paths, list)
            assert ".env" in s.protected_paths
            assert ".git" in s.protected_paths


class TestShellBlocklistStrengthening:

    def test_extra_blocked_patterns_exist(self):
        from tools.shell_tool import ShellTool
        tool = ShellTool()
        with patch("tools.shell_tool.settings") as mock_settings:
            mock_settings.shell_enabled = True
            mock_settings.shell_timeout = 30
            mock_settings.shell_blocked_keywords = ["rm -rf"]

            result = tool.execute("rmdir /s /q C:\\test")
            assert result["success"] is False
            assert "blocked" in result["error"].lower()

    def test_remove_item_blocked(self):
        from tools.shell_tool import ShellTool
        tool = ShellTool()
        with patch("tools.shell_tool.settings") as mock_settings:
            mock_settings.shell_enabled = True
            mock_settings.shell_timeout = 30
            mock_settings.shell_blocked_keywords = []

            result = tool.execute("Remove-Item -Recurse -Force C:\\test")
            assert result["success"] is False

    def test_normal_command_allowed(self):
        from tools.shell_tool import ShellTool
        tool = ShellTool()
        with patch("tools.shell_tool.settings") as mock_settings:
            mock_settings.shell_enabled = True
            mock_settings.shell_timeout = 30
            mock_settings.shell_blocked_keywords = []

            result = tool.execute("dir")
            assert result["success"] is True
