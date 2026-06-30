import subprocess
import logging
import os
import shutil

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

logger = logging.getLogger(__name__)

APP_ALIASES = {
    "google chrome": "chrome",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "file explorer": "explorer",
}

DIRECT_APPS = {
    "vscode": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
    "terminal": "cmd",
    "cmd": "cmd",
    "powershell": "powershell",
    "control panel": "control",
}

URI_APPS = {
    "settings": "ms-settings:",
}

KNOWN_PATHS = {
    "spotify": [
        r"%APPDATA%\Spotify\Spotify.exe",
        r"%LOCALAPPDATA%\Microsoft\WindowsApps\Spotify.exe",
    ],
    "chrome": [
        r"%PROGRAMFILES%\Google\Chrome\Application\chrome.exe",
        r"%PROGRAMFILES(X86)%\Google\Chrome\Application\chrome.exe",
        r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe",
    ],
    "firefox": [
        r"%PROGRAMFILES%\Mozilla Firefox\firefox.exe",
        r"%PROGRAMFILES(X86)%\Mozilla Firefox\firefox.exe",
    ],
}


class AppLauncherTool(BaseTool):

    description = "Opens applications on the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.MEDIUM

    @property
    def name(self):
        return "app_launcher"

    def _find_executable(self, name):
        """Search known install paths and PATH for an executable."""
        if name in KNOWN_PATHS:
            for pattern in KNOWN_PATHS[name]:
                expanded = os.path.expandvars(pattern)
                if os.path.isfile(expanded):
                    return expanded
        found = shutil.which(name)
        if found:
            return found
        return None

    def execute(self, app_name, path=None):

        if not settings.app_launcher_enabled:
            return {
                "success": False,
                "error": "App launcher is disabled"
            }

        name = app_name.strip().lower()
        name = APP_ALIASES.get(name, name)

        logger.info("Launch: %s", name)

        try:
            if name in URI_APPS:
                subprocess.Popen(["start", "", URI_APPS[name]], shell=True)
                return {"success": True, "message": f"Opened {app_name}"}

            if name in DIRECT_APPS:
                cmd = DIRECT_APPS[name]
                cmd_list = [cmd]
                if path:
                    cmd_list.append(path)
                subprocess.Popen(cmd_list)
                return {"success": True, "message": f"Opened {app_name}"}

            exe_path = self._find_executable(name)
            if exe_path:
                cmd_list = [exe_path]
                if path:
                    cmd_list.append(path)
                subprocess.Popen(cmd_list)
                return {"success": True, "message": f"Opened {app_name}"}

            return {
                "success": False,
                "error": f"Could not find '{app_name}' on your system. Try using the full path or install the application first."
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to open {app_name}: {e}"
            }
