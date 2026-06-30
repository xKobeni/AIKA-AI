import subprocess
import logging

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

logger = logging.getLogger(__name__)


class TestRunnerTool(BaseTool):

    description = "Runs Python tests (pytest or unittest)"
    category = ToolCategory.PRODUCTIVITY
    permission = ToolPermission.MEDIUM

    @property
    def name(self):
        return "test_runner"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "path": {
                    "type": "string",
                    "required": False,
                    "description": "Path to test file or directory (default: current directory)"
                },
                "pattern": {
                    "type": "string",
                    "required": False,
                    "description": "Test file pattern, e.g. 'test_*.py'"
                },
                "verbose": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Show verbose output"
                }
            }
        }

    def execute(self, path=None, pattern=None, verbose=True):
        cmd = ["python", "-m", "pytest"]

        if path:
            cmd.append(path)

        if pattern:
            cmd.extend(["-k", pattern])

        if verbose:
            cmd.append("-v")

        cmd.append("--tb=short")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=120
            )

            output = result.stdout
            if result.stderr:
                output += "\n\nSTDERR:\n" + result.stderr

            return {
                "success": result.returncode == 0,
                "output": output[:5000],
                "exit_code": result.returncode,
                "passed": result.returncode == 0
            }

        except FileNotFoundError:
            try:
                cmd = ["python", "-m", "unittest"]
                if path:
                    cmd.append(path)
                if verbose:
                    cmd.append("-v")

                result = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=120
                )

                return {
                    "success": result.returncode == 0,
                    "output": result.stdout[:5000],
                    "exit_code": result.returncode,
                    "passed": result.returncode == 0
                }

            except Exception as e:
                return {"success": False, "error": f"No test runner found: {e}"}

        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Tests timed out after 120s"}

        except Exception as e:
            return {"success": False, "error": str(e)}
