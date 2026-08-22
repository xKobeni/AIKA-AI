from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings
from tools.path_security import iter_scannable_files


class FileSearchTool(BaseTool):

    description = "Searches for files by name in the workspace"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        max_results = getattr(settings, "file_search_max_results", 20)
        max_files = getattr(settings, "file_scan_max_files", 10000)
        self.max_results = max_results if isinstance(max_results, int) else 20
        self.max_files = max_files if isinstance(max_files, int) else 10000

    def refresh_from_settings(self):
        self.__init__()

    @property
    def name(self):

        return "file_search"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "query": {
                    "type": "string",
                    "required": True,
                    "description": "Filename or partial name to search for"
                }
            }
        }

    def execute(
        self,
        query,
        root_path=None
    ):

        if root_path is None:
            root_path = settings.file_search_root_path

        root = Path(root_path).resolve()

        results = []

        for safe_file in iter_scannable_files(
            root, max_files=self.max_files
        ):
            if query.lower() in safe_file.name.lower():
                results.append(str(safe_file))
                if len(results) >= self.max_results:
                    break

        if not results:
            return {
                "success": False,
                "file_paths": [],
                "error": "No files found"
            }

        return {
            "success": True,
            "file_paths": results
        }
