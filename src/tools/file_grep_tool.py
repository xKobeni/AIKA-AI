import re
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import (
    OUTSIDE_WORKSPACE_ERROR,
    iter_scannable_files,
    is_protected_path,
    resolve_workspace_path,
)


class FileGrepTool(BaseTool):

    description = "Searches file contents for text patterns"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.encoding = settings.file_read_encoding
        self.max_results = settings.file_grep_max_results
        max_files = getattr(settings, "file_scan_max_files", 10000)
        self.max_files = max_files if isinstance(max_files, int) else 10000

    def refresh_from_settings(self):
        self.encoding = settings.file_read_encoding
        self.max_results = settings.file_grep_max_results
        max_files = getattr(settings, "file_scan_max_files", 10000)
        self.max_files = max_files if isinstance(max_files, int) else 10000

    @property
    def name(self):
        return "file_grep"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "Text to search for in file contents"
                },
                "path": {
                    "type": "string",
                    "required": False,
                    "default": ".",
                    "description": "Directory to search in"
                },
                "file_pattern": {
                    "type": "string",
                    "required": False,
                    "default": "*",
                    "description": "Glob pattern for files, e.g. '*.py'"
                },
                "recursive": {
                    "type": "boolean",
                    "required": False,
                    "default": True,
                    "description": "Search subdirectories recursively"
                }
            }
        }

    def execute(self, query, path=".", file_pattern="*", recursive=True, root_path=None):

        if not query:
            return {
                "success": False,
                "error": "No search query provided"
            }

        if root_path is None:
            root_path = settings.file_search_root_path

        root, search_path = resolve_workspace_path(root_path, path)
        if search_path is None:
            return {
                "success": False,
                "error": OUTSIDE_WORKSPACE_ERROR
            }

        if is_protected_path(search_path, root):
            return {"success": False, "error": "Access denied: protected path"}

        if not search_path.exists():
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }

        matches = []

        try:
            files = iter_scannable_files(
                root,
                start=search_path,
                recursive=recursive,
                max_files=self.max_files,
            )

            for safe_file in files:

                if file_pattern != "*" and not safe_file.match(file_pattern):
                    continue

                if safe_file.suffix.lower() in [
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
                    ".exe", ".dll", ".so", ".dylib",
                    ".zip", ".tar", ".gz", ".rar",
                    ".db", ".sqlite", ".bin"
                ]:
                    continue

                try:
                    content = safe_file.read_text(
                        encoding=self.encoding,
                        errors="replace"
                    )

                    for i, line in enumerate(content.splitlines(), 1):
                        if query.lower() in line.lower():
                            matches.append({
                                "file": str(safe_file.relative_to(root)),
                                "line_number": i,
                                "line": line.strip()[:200]
                            })

                            if len(matches) >= self.max_results:
                                break

                except Exception:
                    continue

                if len(matches) >= self.max_results:
                    break

            return {
                "success": True,
                "matches": matches,
                "total_matches": len(matches)
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error searching files: {e}"
            }
