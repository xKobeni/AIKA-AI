import os
import re
from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class FileGrepTool(BaseTool):

    description = "Searches file contents for text patterns"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.encoding = settings.file_read_encoding
        self.max_results = settings.file_grep_max_results

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

        root = Path(root_path).resolve()
        search_path = (root / path).resolve()

        if not str(search_path).startswith(str(root) + os.sep) and \
           str(search_path) != str(root):
            return {
                "success": False,
                "error": "Access denied: path is outside workspace"
            }

        if not search_path.exists():
            return {
                "success": False,
                "error": f"Path not found: {path}"
            }

        matches = []

        try:
            glob_pattern = "**/*" if recursive else "*"
            files = search_path.glob(glob_pattern)

            for file_path in files:
                if not file_path.is_file():
                    continue

                if file_pattern != "*" and not file_path.match(file_pattern):
                    continue

                if file_path.suffix.lower() in [
                    ".png", ".jpg", ".jpeg", ".gif", ".bmp",
                    ".exe", ".dll", ".so", ".dylib",
                    ".zip", ".tar", ".gz", ".rar",
                    ".db", ".sqlite", ".bin"
                ]:
                    continue

                try:
                    content = file_path.read_text(
                        encoding=self.encoding,
                        errors="replace"
                    )

                    for i, line in enumerate(content.splitlines(), 1):
                        if query.lower() in line.lower():
                            matches.append({
                                "file": str(file_path.relative_to(root)),
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
