from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class FileReadTool(BaseTool):

    description = "Reads the content of a text file"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_read"

    def execute(self, file_path, root_path=None):

        if root_path is None:
            root_path = settings.file_search_root_path

        root = Path(root_path).resolve()
        path = (root / file_path).resolve()

        if not str(path).startswith(str(root)):
            return {
                "success": False,
                "error": "Access denied: path is outside workspace"
            }

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        if not path.is_file():
            return {
                "success": False,
                "error": f"Not a file: {file_path}"
            }

        try:
            content = path.read_text(
                encoding=self.encoding,
                errors="replace"
            )

            return {
                "success": True,
                "content": content
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error reading file: {e}"
            }
