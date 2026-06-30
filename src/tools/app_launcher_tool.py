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
    "code": [
        r"%LOCALAPPDATA%\Programs\Microsoft VS Code\bin\code.cmd",
        r"%PROGRAMFILES%\Microsoft VS Code\bin\code.cmd",
    ],
    "notepad": [r"%WINDIR%\system32\notepad.exe"],
    "calc": [r"%WINDIR%\system32\calc.exe"],
    "explorer": [r"%WINDIR%\explorer.exe"],
    "cmd": [r"%WINDIR%\system32\cmd.exe"],
    "powershell": [r"%WINDIR%\system32\WindowsPowerShell\v1.0\powershell.exe"],
    "control": [r"%WINDIR%\system32\control.exe"],
}


class AppLauncherTool(BaseTool):

    description = "Opens applications on the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.MEDIUM

    @property
    def name(self):
        return "app_launcher"

    def __init__(self):
        self._app_registry = None

    def _get_registry(self):
        if self._app_registry is None:
            from tools.app_registry import AppRegistry
            self._app_registry = AppRegistry(
                enable_uwp=getattr(settings, 'app_launcher_uwp_enabled', True)
            )
        return self._app_registry

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

    def _fallback_search(self, name):
        """Search using where.exe, known paths, and system app registry."""
        try:
            result = subprocess.run(
                ["where.exe", name],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.strip().split("\n"):
                    path = line.strip()
                    if os.path.isfile(path):
                        return path
        except Exception:
            pass

        resolved = DIRECT_APPS.get(name, name)
        if resolved in KNOWN_PATHS:
            for pattern in KNOWN_PATHS[resolved]:
                expanded = os.path.expandvars(pattern)
                if os.path.isfile(expanded):
                    return expanded

        app_info = self._get_registry().find_app(name)
        if app_info:
            if "path" in app_info:
                return app_info["path"]
            if "aumid" in app_info:
                return app_info["aumid"]

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

        if name in URI_APPS:
            try:
                subprocess.Popen(["start", "", URI_APPS[name]], shell=True)
                return {"success": True, "message": f"Opened {app_name}"}
            except Exception as e:
                return {"success": False, "error": f"Failed to open {app_name}: {e}"}

        cmd_name = DIRECT_APPS.get(name, name)

        try:
            exe_path = self._find_executable(cmd_name)
            cmd_list = [exe_path] if exe_path else [cmd_name]
            if path:
                cmd_list.append(path)
            subprocess.Popen(cmd_list)
            return {"success": True, "message": f"Opened {app_name}"}

        except FileNotFoundError:
            fallback = self._fallback_search(cmd_name)
            if fallback:
                try:
                    if fallback.startswith("shell:AppsFolder") or "!" in fallback:
                        subprocess.Popen(
                            ["start", "", fallback], shell=True
                        )
                    else:
                        cmd_list = [fallback]
                        if path:
                            cmd_list.append(path)
                        subprocess.Popen(cmd_list)
                    return {"success": True, "message": f"Opened {app_name}"}
                except Exception as e:
                    return {"success": False, "error": f"Failed to open {app_name}: {e}"}
            return {
                "success": False,
                "error": f"Could not find '{app_name}' on your system."
            }

        except Exception as e:
            return {
                "success": False,
                "error": f"Failed to open {app_name}: {e}"
            }
