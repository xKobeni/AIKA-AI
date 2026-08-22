import subprocess
import logging
import os
import re
import shlex
from pathlib import Path

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import OUTSIDE_WORKSPACE_ERROR, resolve_workspace_path

logger = logging.getLogger(__name__)


class ShellTool(BaseTool):

    description = "Executes shell commands on the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.HIGH

    @property
    def name(self):
        return "shell"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "command": {
                    "type": "string",
                    "required": True,
                    "description": "Shell command to execute"
                },
                "timeout": {
                    "type": "integer",
                    "required": False,
                    "description": "Timeout in seconds (default from settings)"
                },
                "workdir": {
                    "type": "string",
                    "required": False,
                    "description": "Working directory for the command"
                },
                "unsafe": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Use the system shell; requires SHELL_UNSAFE_ENABLED=true"
                }
            }
        }

    @staticmethod
    def _split_command(command):
        if isinstance(command, (list, tuple)):
            return [str(part) for part in command if str(part)]
        if not isinstance(command, str) or not command.strip():
            return []
        if re.search(r"(?:&&|\|\||[|;&<>`\n\r])", command):
            raise ValueError(
                "Shell operators are not allowed in safe mode; "
                "use explicit arguments or enable unsafe shell mode"
            )
        parts = shlex.split(command, posix=os.name != "nt")
        if os.name == "nt":
            parts = [
                part[1:-1] if len(part) >= 2 and part[0] == part[-1] == '"'
                else part
                for part in parts
            ]
        return parts

    @staticmethod
    def _resolve_workdir(workdir):
        configured_root = getattr(settings, "file_search_root_path", ".")
        if not isinstance(configured_root, (str, Path)):
            configured_root = "."
        root, target = resolve_workspace_path(configured_root, workdir or ".")
        if target is None or not target.is_dir():
            return None, OUTSIDE_WORKSPACE_ERROR

        allowed = getattr(settings, "shell_allowed_workdirs", ["."])
        if not isinstance(allowed, list):
            allowed = ["."]
        for allowed_path in allowed:
            _, allowed_target = resolve_workspace_path(root, allowed_path)
            if allowed_target is None:
                continue
            try:
                target.relative_to(allowed_target)
                return target, None
            except ValueError:
                continue
        return None, "Access denied: shell working directory is not allowed"

    def execute(self, command, timeout=None, workdir=None, unsafe=False):

        if not settings.shell_enabled:
            return {
                "success": False,
                "error": "Shell execution is disabled"
            }

        configured_timeout = getattr(settings, "shell_timeout", 30)
        if not isinstance(configured_timeout, int):
            configured_timeout = 30
        if timeout is None:
            timeout = configured_timeout
        try:
            timeout = min(max(1, int(timeout)), configured_timeout)
        except (TypeError, ValueError):
            return {"success": False, "error": "Invalid command timeout"}

        command_text = (
            " ".join(str(part) for part in command)
            if isinstance(command, (list, tuple)) else str(command)
        )
        text = command_text.lower()

        blocked = settings.shell_blocked_keywords
        for keyword in blocked:
            kw = keyword.lower().strip()
            if kw and kw in text:
                logger.warning("Blocked command keyword: %s", keyword)
                return {
                    "success": False,
                    "error": f"Command blocked: contains '{keyword}'"
                }

        extra_blocked = [
            "rmdir /s", "remove-item -recurse", "remove-item -force",
            "del /f /q", "rm -r -f", "rm  -rf",
            "cmd /c del", "cmd /c format",
            "bcdedit", "diskpart", "bootcfg",
            "net user", "net localgroup administrators",
            "reg add", "reg delete",
            "attrib -r -s -h",
            "icacls", "takeown",
        ]
        for pattern in extra_blocked:
            if pattern in text:
                logger.warning("Blocked command pattern: %s", pattern)
                return {
                    "success": False,
                    "error": f"Command blocked: matches restricted pattern"
                }

        resolved_workdir, workdir_error = self._resolve_workdir(workdir)
        if resolved_workdir is None:
            return {"success": False, "error": workdir_error}

        if unsafe and not getattr(settings, "shell_unsafe_enabled", False):
            return {
                "success": False,
                "error": "Unsafe shell mode is disabled"
            }

        try:
            args = command_text if unsafe else self._split_command(command)
        except ValueError as e:
            return {"success": False, "error": str(e)}

        if not args:
            return {"success": False, "error": "No command provided"}

        if len(args) > 2:
            combined_path = " ".join(args[1:])
            if Path(combined_path).is_file():
                args = [args[0], combined_path]

        logger.info("Shell safe=%s: %s", not unsafe, command_text)

        if not unsafe and args[0].lower() == "echo":
            return {
                "success": True,
                "stdout": " ".join(args[1:]) + "\n",
                "stderr": "",
                "exit_code": 0,
            }

        if not unsafe and args[0].lower() == "dir" and len(args) == 1:
            return {
                "success": True,
                "stdout": "\n".join(
                    entry.name for entry in resolved_workdir.iterdir()
                ) + "\n",
                "stderr": "",
                "exit_code": 0,
            }

        try:
            result = subprocess.run(
                args,
                shell=bool(unsafe),
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(resolved_workdir)
            )

            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Command timed out after {timeout}s"
            }

        except FileNotFoundError as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "exit_code": 127,
                "error": "Executable not found",
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
