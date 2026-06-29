import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

import pytest

from tools.shell_tool import ShellTool
from tools.app_launcher_tool import AppLauncherTool
from tools.folder_tool import FolderTool
from tools.system_info_tool import SystemInfoTool
from brain.decision_engine import DecisionEngine
from config.settings import settings


@pytest.fixture
def shell_tool():
    return ShellTool()


@pytest.fixture
def app_launcher_tool():
    return AppLauncherTool()


@pytest.fixture
def folder_tool():
    return FolderTool()


@pytest.fixture
def system_info_tool():
    return SystemInfoTool()


@pytest.fixture
def decision_engine():
    return DecisionEngine()


@pytest.fixture
def temp_workspace(tmp_path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "subdir").mkdir()
    (workspace / "file_a.txt").write_text("hello")
    (workspace / "file_b.py").write_text("print('hi')")
    return workspace


@pytest.fixture
def sandboxed_folder(folder_tool, temp_workspace):
    old = settings.file_search_root_path
    settings.file_search_root_path = str(temp_workspace)
    yield folder_tool, temp_workspace
    settings.file_search_root_path = old
