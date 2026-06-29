from models.actions import Action
from config.settings import settings


class TestShellTool:

    def test_basic_command(self, shell_tool):
        result = shell_tool.execute("echo hello")
        assert result["success"] is True
        assert "hello" in result["stdout"]

    def test_blocked_keyword(self, shell_tool):
        result = shell_tool.execute("rm -rf /")
        assert result["success"] is False
        assert "blocked" in result["error"]

    def test_exit_code_zero(self, shell_tool):
        result = shell_tool.execute("python -c exit(0)")
        assert result["exit_code"] == 0

    def test_exit_code_nonzero(self, shell_tool):
        result = shell_tool.execute("python -c exit(42)")
        assert result["exit_code"] != 0

    def test_stderr_captured(self, shell_tool, tmp_path):
        script = tmp_path / "test_stderr.py"
        script.write_text('import sys; sys.stderr.write("error msg")')
        result = shell_tool.execute(f"python {script}")
        assert "error msg" in result["stderr"]

    def test_stdout_and_stderr_separate(self, shell_tool, tmp_path):
        script = tmp_path / "test_sep.py"
        script.write_text(
            'import sys; sys.stdout.write("out"); sys.stderr.write("err")'
        )
        result = shell_tool.execute(f"python {script}")
        assert "out" in result["stdout"]
        assert "err" in result["stderr"]

    def test_tool_metadata(self, shell_tool):
        assert shell_tool.name == "shell"
        assert shell_tool.description
        assert shell_tool.category.value == "system"
        assert shell_tool.permission.value == "high"


class TestAppLauncherTool:

    def test_unknown_app_returns_message(self, app_launcher_tool):
        result = app_launcher_tool.execute(
            "this_app_does_not_exist_xyz_12345"
        )
        assert "message" in result or "error" in result

    def test_tool_metadata(self, app_launcher_tool):
        assert app_launcher_tool.name == "app_launcher"
        assert app_launcher_tool.description
        assert app_launcher_tool.category.value == "system"


class TestFolderTool:

    def test_list_root(self, sandboxed_folder):
        tool, workspace = sandboxed_folder
        result = tool.execute(".")
        assert result["success"] is True
        assert result["folder_count"] >= 1
        assert "subdir/" in result["folders"]
        assert result["file_count"] >= 2

    def test_list_subdir(self, sandboxed_folder):
        tool, workspace = sandboxed_folder
        result = tool.execute("subdir")
        assert result["success"] is True
        assert result["folder_count"] >= 0

    def test_traversal_blocked(self, sandboxed_folder):
        tool, workspace = sandboxed_folder
        result = tool.execute("../../")
        assert result["success"] is False
        assert "outside workspace" in result["error"]

    def test_nonexistent_path(self, folder_tool):
        result = folder_tool.execute("does_not_exist_xyz_12345")
        assert result["success"] is False
        assert "not found" in result["error"]

    def test_file_path_returns_not_a_dir(self, sandboxed_folder):
        tool, workspace = sandboxed_folder
        result = tool.execute("file_a.txt")
        assert result["success"] is False
        assert "Not a directory" in result["error"]
        assert result.get("is_file") is True

    def test_tool_metadata(self, folder_tool):
        assert folder_tool.name == "folder"
        assert folder_tool.description
        assert folder_tool.category.value == "system"


class TestSystemInfoTool:

    def test_basic_fields(self, system_info_tool):
        result = system_info_tool.execute()
        assert result["success"] is True
        info_text = "\n".join(result["info"])
        assert "Python" in info_text
        assert "OS" in info_text or "Windows" in info_text

    def test_text_field_present(self, system_info_tool):
        result = system_info_tool.execute()
        assert "text" in result
        assert len(result["text"]) > 0

    def test_tool_metadata(self, system_info_tool):
        assert system_info_tool.name == "system_info"
        assert system_info_tool.description
        assert system_info_tool.category.value == "system"
        assert system_info_tool.permission.value == "low"


class TestDecisionEngine:

    def test_run_command(self, decision_engine):
        assert decision_engine.decide("run pip install requests") == Action.USE_TOOL

    def test_open_app(self, decision_engine):
        assert decision_engine.decide("open spotify") == Action.USE_TOOL

    def test_list_path(self, decision_engine):
        assert decision_engine.decide("list src folder") == Action.USE_TOOL

    def test_show_path(self, decision_engine):
        assert decision_engine.decide("show files") == Action.USE_TOOL

    def test_system_info(self, decision_engine):
        assert decision_engine.decide("system info") == Action.USE_TOOL

    def test_system_health(self, decision_engine):
        assert decision_engine.decide("system health") == Action.USE_TOOL

    def test_how_is_my_system(self, decision_engine):
        assert decision_engine.decide("how's my system") == Action.USE_TOOL

    def test_greeting_not_routed(self, decision_engine):
        assert decision_engine.decide("hello") != Action.USE_TOOL

    def test_question_not_routed(self, decision_engine):
        assert decision_engine.decide("what is python") != Action.USE_TOOL


class TestSettings:

    def test_shell_timeout_default(self):
        assert hasattr(settings, "shell_timeout")
        assert settings.shell_timeout == 30

    def test_blocked_keywords_list(self):
        assert hasattr(settings, "shell_blocked_keywords")
        assert isinstance(settings.shell_blocked_keywords, list)
        assert "rm -rf" in settings.shell_blocked_keywords
        assert "shutdown" in settings.shell_blocked_keywords

    def test_shell_enabled_default(self):
        assert hasattr(settings, "shell_enabled")
        assert settings.shell_enabled is True
