from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_workspace_path,
)


class FileReadRangeTool(BaseTool):

    description = "Reads specific line ranges from a file"
    category = ToolCategory.FILE
    permission = ToolPermission.LOW

    def __init__(self):
        self.encoding = settings.file_read_encoding

    def refresh_from_settings(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_read_range"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "file_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the file to read"
                },
                "start_line": {
                    "type": "integer",
                    "required": False,
                    "description": "Starting line number (1-indexed)"
                },
                "end_line": {
                    "type": "integer",
                    "required": False,
                    "description": "Ending line number (inclusive)"
                }
            }
        }

    def execute(self, file_path, start_line=None, end_line=None, root_path=None):
        if root_path is None:
            root_path = settings.file_search_root_path

        root, path = resolve_workspace_path(root_path, file_path)
        if path is None:
            return {"success": False, "error": OUTSIDE_WORKSPACE_ERROR}
        if is_protected_path(path, root):
            return {"success": False, "error": "Access denied: protected path"}

        if not path.exists():
            return {"success": False, "error": f"File not found: {file_path}"}

        if not path.is_file():
            return {"success": False, "error": f"Not a file: {file_path}"}

        try:
            content = path.read_text(encoding=self.encoding, errors="replace")
            lines = content.splitlines()

            total_lines = len(lines)

            start = (start_line - 1) if start_line else 0
            end = end_line if end_line else total_lines

            start = max(0, start)
            end = min(total_lines, end)

            selected = lines[start:end]

            numbered = []
            for i, line in enumerate(selected, start=start + 1):
                numbered.append(f"{i}: {line}")

            return {
                "success": True,
                "content": "\n".join(numbered),
                "total_lines": total_lines,
                "start_line": start + 1,
                "end_line": end,
            }

        except Exception as e:
            return {"success": False, "error": f"Error reading file: {e}"}
