import logging
import os

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    DEFAULT_SCAN_EXCLUDED_DIRS,
    is_protected_path,
    resolve_known_user_folder,
    resolve_workspace_path,
    resolve_user_scoped_path,
)

logger = logging.getLogger(__name__)


class FolderTool(BaseTool):

    description = (
        "Lists a contained workspace or Desktop directory, or the read-only "
        "root of the current user's Downloads folder"
    )
    category = ToolCategory.SYSTEM
    permission = ToolPermission.MEDIUM
    response_policy = "action_confirmation"

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
                    "description": (
                        "Contained workspace path, desktop, or downloads "
                        "(non-hidden root listing only)"
                    )
                },
                "show_hidden": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Include hidden files (starting with .)"
                },
                "find": {
                    "type": "string",
                    "required": False,
                    "description": "Folder name to find under the selected path"
                },
                "open_match": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Open the matched folder in File Explorer"
                }
            }
        }

    def _find_directory(self, root, query):
        wanted = str(query).strip().lower()
        if wanted.endswith(" folder"):
            wanted = wanted[:-7].strip()
        partial_match = None
        scanned = 0
        max_dirs = max(1, int(getattr(settings, "file_scan_max_files", 10000)))

        for current, dirnames, _ in os.walk(root, followlinks=False):
            current_path = type(root)(current)
            allowed = []
            for dirname in dirnames:
                candidate = current_path / dirname
                _, safe_candidate = resolve_workspace_path(root, candidate)
                if safe_candidate is None:
                    continue
                if dirname.lower() in DEFAULT_SCAN_EXCLUDED_DIRS:
                    continue
                if is_protected_path(safe_candidate, root):
                    continue
                allowed.append(dirname)
                scanned += 1
                lowered = dirname.lower()
                if lowered == wanted:
                    return safe_candidate
                if partial_match is None and wanted in lowered:
                    partial_match = safe_candidate
                if scanned >= max_dirs:
                    dirnames[:] = []
                    return partial_match
            dirnames[:] = allowed
        return partial_match

    @staticmethod
    def _resolve_listing_path(path):
        requested = str(path or ".").strip()
        if requested.lower() in {"download", "downloads"}:
            root = resolve_known_user_folder("downloads")
            if root is None:
                return resolve_workspace_path(
                    settings.file_search_root_path, "../__outside__"
                )
            return resolve_workspace_path(root, ".")
        return resolve_user_scoped_path(
            settings.file_search_root_path, requested
        )

    def execute(
        self, path=".", show_hidden=False, find=None, open_match=False
    ):

        downloads_listing = str(path or ".").strip().lower() in {
            "download", "downloads"
        }
        if downloads_listing and (show_hidden or find or open_match):
            return {
                "success": False,
                "error": (
                    "Downloads access is limited to a non-hidden root listing"
                ),
            }

        root, target = self._resolve_listing_path(path)
        if target is None:
            if downloads_listing:
                return {
                    "success": False,
                    "error": "The Downloads folder is unavailable",
                }
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

        if find:
            match = self._find_directory(target, find)
            if match is None:
                return {
                    "success": False,
                    "error": f"Could not find folder '{find}' under {target}",
                }
            if open_match:
                if os.name != "nt":
                    return {
                        "success": False,
                        "error": "Opening folders is only supported on Windows",
                    }
                try:
                    os.startfile(str(match))
                except Exception as exc:
                    return {
                        "success": False,
                        "error": f"Could not open folder: {type(exc).__name__}",
                    }
                return {
                    "success": True,
                    "path": str(match),
                    "message": f"Opened {match.name} folder",
                }
            target = match

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
