from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_workspace_path,
)


class FileWriteTool(BaseTool):

    description = "Creates or writes content to a text file"
    category = ToolCategory.FILE
    permission = ToolPermission.HIGH

    def __init__(self):
        self.encoding = settings.file_read_encoding

    def refresh_from_settings(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_write"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "file_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the file to write"
                },
                "content": {
                    "type": "string",
                    "required": True,
                    "description": "Content to write to the file"
                }
            }
        }

    def _is_protected_path(self, file_path):
        return is_protected_path(file_path)

    def execute(self, file_path, content, root_path=None):

        if not settings.file_write_enabled:
            return {
                "success": False,
                "error": "File write is disabled"
            }

        if not content and content != "":
            return {
                "success": False,
                "error": "No content provided"
            }

        if len(content) > 1_000_000:
            return {
                "success": False,
                "error": f"Content too large ({len(content)} chars). Maximum is 1MB."
            }

        if root_path is None:
            root_path = settings.file_search_root_path

        root, path = resolve_workspace_path(root_path, file_path)
        if path is None:
            return {
                "success": False,
                "error": OUTSIDE_WORKSPACE_ERROR
            }

        if is_protected_path(path, root):
            return {
                "success": False,
                "error": f"Cannot write to protected path: {file_path}"
            }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            bytes_written = path.write_text(
                content,
                encoding=self.encoding
            )

            return {
                "success": True,
                "file_path": str(path),
                "bytes_written": bytes_written
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error writing file: {e}"
            }
