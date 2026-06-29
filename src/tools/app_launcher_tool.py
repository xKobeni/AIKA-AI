import subprocess
import logging
import shlex

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

logger = logging.getLogger(__name__)

APP_ALIASES = {
    "spotify": ["start", "spotify"],
    "chrome": ["start", "chrome"],
    "google chrome": ["start", "chrome"],
    "firefox": ["start", "firefox"],
    "vscode": ["code"],
    "vs code": ["code"],
    "visual studio code": ["code"],
    "notepad": ["notepad"],
    "calculator": ["calc"],
    "explorer": ["explorer"],
    "file explorer": ["explorer"],
    "terminal": ["start", "cmd"],
    "cmd": ["start", "cmd"],
    "powershell": ["start", "powershell"],
    "settings": ["start", "ms-settings:"],
    "control panel": ["control"],
}


class AppLauncherTool(BaseTool):

    description = "Opens applications on the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.MEDIUM

    @property
    def name(self):
        return "app_launcher"

    def execute(self, app_name, path=None):

        if not settings.app_launcher_enabled:
            return {
                "success": False,
                "error": "App launcher is disabled"
            }

        name = app_name.strip().lower()

        cmd = APP_ALIASES.get(name)
        if cmd:
            cmd_list = list(cmd)
        else:
            cmd_list = ["start", name]

        if path:
            cmd_list.append(path)

        logger.info("Launch: %s", " ".join(cmd_list))

        try:
            if cmd_list[0] == "start":
                subprocess.Popen(
                    cmd_list,
                    shell=True
                )
            else:
                subprocess.Popen(cmd_list)

            return {
                "success": True,
                "message": f"Opened {app_name}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to open {app_name}: {e}"
            }
