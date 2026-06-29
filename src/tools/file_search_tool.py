from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class FileSearchTool(BaseTool):

    description = "Searches for files by name in the workspace"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.max_results = 20

    @property
    def name(self):

        return "file_search"

    def execute(
        self,
        query,
        root_path=None
    ):

        if root_path is None:
            root_path = settings.file_search_root_path

        root = Path(root_path).resolve()

        results = []

        for file in root.rglob("*"):

            if file.is_file() and query.lower() in file.name.lower():

                results.append(str(file))

        if not results:
            return {
                "success": False,
                "file_paths": [],
                "error": "No files found"
            }

        return {
            "success": True,
            "file_paths": results[:self.max_results]
        }
