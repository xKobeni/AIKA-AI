import subprocess
import logging
import os
import shutil

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_user_scoped_path,
)
from config.settings import settings

logger = logging.getLogger(__name__)

APP_ALIASES = {
    "calc": "calculator",
    "code": "vscode",
    "google chrome": "chrome",
    "vs code": "vscode",
    "visual studio code": "vscode",
    "file explorer": "explorer",
    "command prompt": "cmd",
    "control panel": "control",
    "wt": "terminal",
    "windows terminal": "terminal",
}

DIRECT_APPS = {
    "vscode": "code",
    "notepad": "notepad",
    "calculator": "calc",
    "explorer": "explorer",
    "terminal": "wt",
    "cmd": "cmd",
    "powershell": "powershell",
    "control": "control",
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
    "wt": [r"%LOCALAPPDATA%\Microsoft\WindowsApps\wt.exe"],
    "cmd": [r"%WINDIR%\system32\cmd.exe"],
    "powershell": [r"%WINDIR%\system32\WindowsPowerShell\v1.0\powershell.exe"],
    "control": [r"%WINDIR%\system32\control.exe"],
}

ALLOWED_APPS = frozenset({
    "file",
    "camera",
    "chrome",
    "spotify",
    "firefox",
    "vscode",
    "notepad",
    "calculator",
    "explorer",
    "terminal",
    "cmd",
    "powershell",
    "control",
    "settings",
})

SAFE_FILE_EXTENSIONS = frozenset({
    ".txt", ".md", ".pdf", ".rtf", ".odt",
    ".doc", ".docx", ".xls", ".xlsx", ".csv", ".tsv",
    ".ppt", ".pptx",
    ".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".svg",
    ".mp3", ".wav", ".m4a", ".mp4", ".mov", ".avi", ".mkv",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".log",
})


class AppLauncherTool(BaseTool):

    description = "Opens applications on the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.MEDIUM
    response_policy = "action_confirmation"

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

    def _launch_process(self, command, *, new_console=False):
        kwargs = {}
        if new_console and os.name == "nt":
            kwargs["creationflags"] = subprocess.CREATE_NEW_CONSOLE
        return subprocess.Popen(command, **kwargs)

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

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "app_name": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "Approved application name, or 'file' to open a "
                        "contained file path"
                    )
                },
                "path": {
                    "type": "string",
                    "required": False,
                    "description": "File path; valid only when app_name is 'file'"
                }
            }
        }

    def execute(self, app_name, path=None):

        if not settings.app_launcher_enabled:
            return {
                "success": False,
                "error": "App launcher is disabled"
            }

        if not isinstance(app_name, str) or not app_name.strip():
            return {
                "success": False,
                "error": "Application name must be a non-empty string",
            }

        name = app_name.strip().lower()
        name = APP_ALIASES.get(name, name)

        logger.info("Launch: %s", name)

        if name not in ALLOWED_APPS:
            return {
                "success": False,
                "error": f"Unsupported application: {app_name}",
            }

        if name == "file":
            if not path:
                return {"success": False, "error": "No file path provided"}
            root, target = resolve_user_scoped_path(
                settings.file_search_root_path, path
            )
            if target is None:
                return {"success": False, "error": OUTSIDE_WORKSPACE_ERROR}
            if is_protected_path(target, root):
                return {"success": False, "error": "Access denied: protected path"}
            if not target.is_file():
                return {
                    "success": False,
                    "error": f"File not found: {path}",
                }
            extension = target.suffix.lower()
            if extension not in SAFE_FILE_EXTENSIONS:
                display_extension = extension or "files without an extension"
                return {
                    "success": False,
                    "error": (
                        "File type is not allowed for launching: "
                        f"{display_extension}"
                    ),
                }
            if os.name != "nt":
                return {
                    "success": False,
                    "error": "Opening files is only supported on Windows",
                }
            try:
                os.startfile(str(target))
                return {
                    "success": True,
                    "path": str(target),
                    "message": f"Opened {target.name}",
                }
            except Exception as exc:
                return {
                    "success": False,
                    "error": f"Failed to open file: {type(exc).__name__}",
                }

        if path is not None:
            return {
                "success": False,
                "error": "Application arguments are not supported",
            }

        if name in URI_APPS:
            try:
                if os.name != "nt":
                    return {
                        "success": False,
                        "error": f"'{app_name}' is only available on Windows"
                    }
                os.startfile(URI_APPS[name])
                return {"success": True, "message": f"Opened {app_name}"}
            except Exception as e:
                return {"success": False, "error": f"Failed to open {app_name}: {e}"}

        cmd_name = DIRECT_APPS.get(name, name)
        new_console = name in {"cmd", "powershell"}

        try:
            exe_path = self._find_executable(cmd_name)
            cmd_list = [exe_path] if exe_path else [cmd_name]
            self._launch_process(cmd_list, new_console=new_console)
            return {"success": True, "message": f"Opened {app_name}"}

        except FileNotFoundError:
            fallback = self._fallback_search(name)
            if fallback:
                try:
                    if "!" in fallback:
                        self._launch_process(
                            ["explorer.exe", f"shell:AppsFolder\\{fallback}"]
                        )
                    else:
                        cmd_list = [fallback]
                        self._launch_process(
                            cmd_list, new_console=new_console
                        )
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
