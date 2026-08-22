import logging

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    is_protected_path,
    resolve_workspace_path,
)

logger = logging.getLogger(__name__)


class FolderTool(BaseTool):

    description = "Lists contents of a directory"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.MEDIUM

    @property
    def name(self):
        return "folder"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "path": {
                    "type": "string",
                    "required": False,
                    "default": ".",
                    "description": "Directory path to list"
                },
                "show_hidden": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Include hidden files (starting with .)"
                }
            }
        }

    def execute(self, path=".", show_hidden=False):

        root, target = resolve_workspace_path(
            settings.file_search_root_path, path
        )
        if target is None:
            return {
                "success": False,
                "error": OUTSIDE_WORKSPACE_ERROR
            }

        if is_protected_path(target, root):
            return {"success": False, "error": "Access denied: protected path"}

        if not target.exists():
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }

        if not target.is_dir():
            return {
                "success": False,
                "error": f"Not a directory: {path}",
                "is_file": True,
                "file_path": str(target)
            }

        try:
            entries = sorted(
                target.iterdir(),
                key=lambda e: (not e.is_dir(), e.name.lower())
            )

            folders = []
            files = []

            for entry in entries:
                _, safe_entry = resolve_workspace_path(root, entry)
                if safe_entry is None or is_protected_path(safe_entry, root):
                    continue
                if entry.name.startswith(".") and not show_hidden:
                    continue
                if entry.is_dir():
                    folders.append(entry.name + "/")
                else:
                    size = ""
                    try:
                        size = entry.stat().st_size
                        if size < 1024:
                            size = f" ({size} B)"
                        elif size < 1024 ** 2:
                            size = f" ({size // 1024} KB)"
                        else:
                            size = f" ({size // (1024 ** 2)} MB)"
                    except OSError:
                        pass
                    files.append(entry.name + size)

            return {
                "success": True,
                "path": str(target),
                "folders": folders,
                "files": files,
                "folder_count": len(folders),
                "file_count": len(files)
            }

        except PermissionError:
            return {
                "success": False,
                "error": f"Permission denied: {path}"
            }

        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }
