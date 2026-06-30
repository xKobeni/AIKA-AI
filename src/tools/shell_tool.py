import subprocess
import logging
import shlex

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

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
                }
            }
        }

    def execute(self, command, timeout=None, workdir=None):

        if not settings.shell_enabled:
            return {
                "success": False,
                "error": "Shell execution is disabled"
            }

        if timeout is None:
            timeout = settings.shell_timeout

        text = command.lower()

        blocked = settings.shell_blocked_keywords
        for keyword in blocked:
            kw = keyword.lower().strip()
            if kw and kw in text:
                logger.warning("Blocked command keyword: %s", keyword)
                return {
                    "success": False,
                    "error": f"Command blocked: contains '{keyword}'"
                }

        logger.info("Shell: %s", command)

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=workdir
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

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
