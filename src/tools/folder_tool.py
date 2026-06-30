import os
import logging
from pathlib import Path

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

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

        root = Path(settings.file_search_root_path).resolve()
        target = (root / path).resolve()

        if not str(target).startswith(str(root)):
            return {
                "success": False,
                "error": "Access denied: path is outside workspace"
            }

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
