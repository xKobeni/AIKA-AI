from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class FileReadTool(BaseTool):

    description = "Reads the content of a text file"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    @property
    def name(self):
        return "file_read"

    def execute(self, file_path, root_path="."):

        path = Path(root_path) / file_path

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        if not path.is_file():
            return {
                "success": False,
                "error": f"Not a file: {file_path}"
            }

        try:
            content = path.read_text(
                encoding="utf-8",
                errors="replace"
            )

            return {
                "success": True,
                "content": content
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error reading file: {e}"
            }
