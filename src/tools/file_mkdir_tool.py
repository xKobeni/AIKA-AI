from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_workspace_path,
)


class FileMkdirTool(BaseTool):

    description = "Creates a directory"
    category = ToolCategory.FILE
    permission = ToolPermission.HIGH

    @property
    def name(self):
        return "file_mkdir"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "dir_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path of the directory to create"
                },
                "parents": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Create parent directories if needed"
                }
            }
        }

    def execute(self, dir_path, parents=True, root_path=None):

        if not settings.file_write_enabled:
            return {
                "success": False,
                "error": "File write is disabled"
            }

        if root_path is None:
            root_path = settings.file_search_root_path

        root, path = resolve_workspace_path(root_path, dir_path)
        if path is None:
            return {
                "success": False,
                "error": OUTSIDE_WORKSPACE_ERROR
            }

        if is_protected_path(path, root):
            return {"success": False, "error": "Cannot create protected path"}

        if path.exists():
            return {
                "success": False,
                "error": f"Directory already exists: {dir_path}"
            }

        try:
            path.mkdir(parents=parents, exist_ok=False)

            return {
                "success": True,
                "dir_path": str(path),
                "message": f"Created directory: {dir_path}"
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error creating directory: {e}"
            }
