from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_workspace_path,
)


class FileReadTool(BaseTool):

    description = "Reads the content of a text file"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.encoding = settings.file_read_encoding

    def refresh_from_settings(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_read"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "file_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the file to read"
                }
            }
        }

    def execute(self, file_path, root_path=None):

        if root_path is None:
            root_path = settings.file_search_root_path

        root, path = resolve_workspace_path(root_path, file_path)
        if path is None:
            return {
                "success": False,
                "error": OUTSIDE_WORKSPACE_ERROR
            }

        if is_protected_path(path, root):
            return {"success": False, "error": "Access denied: protected path"}

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
                encoding=self.encoding,
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
