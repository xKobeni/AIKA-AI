from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class FileAppendTool(BaseTool):

    description = "Appends content to the end of a file"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_append"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "file_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the file to append to"
                },
                "content": {
                    "type": "string",
                    "required": True,
                    "description": "Content to append to the file"
                }
            }
        }

    def execute(self, file_path, content, root_path=None):

        if not settings.file_write_enabled:
            return {
                "success": False,
                "error": "File write is disabled"
            }

        if content is None:
            return {
                "success": False,
                "error": "No content provided"
            }

        if root_path is None:
            root_path = settings.file_search_root_path

        root = Path(root_path).resolve()
        path = (root / file_path).resolve()

        if not str(path).startswith(str(root)):
            return {
                "success": False,
                "error": "Access denied: path is outside workspace"
            }

        try:
            path.parent.mkdir(parents=True, exist_ok=True)

            with open(path, "a", encoding=self.encoding) as f:
                bytes_written = f.write(content)

            return {
                "success": True,
                "file_path": str(path),
                "bytes_appended": bytes_written
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error appending to file: {e}"
            }
