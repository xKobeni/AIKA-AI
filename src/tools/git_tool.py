import subprocess
import logging

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

logger = logging.getLogger(__name__)


class GitTool(BaseTool):

    description = "Performs git operations (status, diff, log, commit, branch)"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.HIGH

    @property
    def name(self):
        return "git"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "action": {
                    "type": "string",
                    "required": True,
                    "description": "Git action: status, diff, log, commit, branch, checkout, add"
                },
                "message": {
                    "type": "string",
                    "required": False,
                    "description": "Commit message (for commit action)"
                },
                "branch": {
                    "type": "string",
                    "required": False,
                    "description": "Branch name (for branch/checkout actions)"
                },
                "files": {
                    "type": "string",
                    "required": False,
                    "description": "Space-separated file paths (for add action)"
                }
            }
        }

    def execute(self, action, message=None, branch=None, files=None):
        if not settings.shell_enabled:
            return {"success": False, "error": "Shell execution is disabled"}

        action = action.lower().strip()

        if action == "status":
            return self._run_git(["git", "status"])
        elif action == "diff":
            return self._run_git(["git", "diff"])
        elif action == "log":
            return self._run_git(["git", "log", "--oneline", "-20"])
        elif action == "add":
            if not files:
                return {"success": False, "error": "No files specified for git add"}
            file_list = files.split()
            return self._run_git(["git", "add"] + file_list)
        elif action == "commit":
            if not message:
                return {"success": False, "error": "No commit message provided"}
            return self._run_git(["git", "commit", "-m", message])
        elif action == "branch":
            if branch:
                return self._run_git(["git", "branch", branch])
            return self._run_git(["git", "branch"])
        elif action == "checkout":
            if not branch:
                return {"success": False, "error": "No branch specified for checkout"}
            return self._run_git(["git", "checkout", branch])
        else:
            return {"success": False, "error": f"Unknown git action: {action}"}

    def _run_git(self, cmd_list):
        try:
            result = subprocess.run(
                cmd_list,
                capture_output=True,
                text=True,
                timeout=30
            )
            output = result.stdout.strip()
            if result.returncode != 0:
                output = result.stderr.strip() or output
            return {
                "success": result.returncode == 0,
                "output": output,
                "exit_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Git command timed out"}
        except Exception as e:
            return {"success": False, "error": str(e)}
