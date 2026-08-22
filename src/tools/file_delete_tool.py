import shutil
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_workspace_path,
)


class FileDeleteTool(BaseTool):

    description = "Deletes a file or directory"
    category = ToolCategory.FILE
    permission = ToolPermission.HIGH

    @property
    def name(self):
        return "file_delete"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "file_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the file or directory to delete"
                },
                "recursive": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "If true, delete directories recursively"
                }
            }
        }

    def _is_protected_path(self, file_path):
        return is_protected_path(file_path)

    def execute(self, file_path, recursive=False, root_path=None):

        if not settings.file_delete_enabled:
            return {
                "success": False,
                "error": "File delete is disabled"
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
                "error": f"Cannot delete protected path: {file_path}"
            }

        if not path.exists():
            return {
                "success": False,
                "error": f"Path not found: {file_path}"
            }

        try:
            if path.is_dir():
                if not recursive:
                    contents = list(path.iterdir())
                    if contents:
                        return {
                            "success": False,
                            "error": f"Directory not empty: {file_path}. Use recursive=true to delete"
                        }
                shutil.rmtree(path)
            else:
                path.unlink()

            return {
                "success": True,
                "file_path": str(path),
                "message": f"Deleted: {file_path}"
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error deleting: {e}"
            }
