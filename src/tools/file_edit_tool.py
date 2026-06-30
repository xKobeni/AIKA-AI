from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class FileEditTool(BaseTool):

    description = "Finds and replaces text in a file"
    category = ToolCategory.FILE
    permission = ToolPermission.MEDIUM

    def __init__(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_edit"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "file_path": {
                    "type": "string",
                    "required": True,
                    "description": "Path to the file to edit"
                },
                "old_text": {
                    "type": "string",
                    "required": True,
                    "description": "Text to find and replace"
                },
                "new_text": {
                    "type": "string",
                    "required": True,
                    "description": "Replacement text"
                },
                "replace_all": {
                    "type": "boolean",
                    "required": False,
                    "default": False,
                    "description": "Replace all occurrences or just the first"
                }
            }
        }

    def execute(self, file_path, old_text, new_text, replace_all=False, root_path=None):

        if not settings.file_write_enabled:
            return {
                "success": False,
                "error": "File write is disabled"
            }

        if not old_text:
            return {
                "success": False,
                "error": "No search text provided"
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

        if not path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}"
            }

        try:
            content = path.read_text(encoding=self.encoding)

            if old_text not in content:
                return {
                    "success": False,
                    "error": f"Text not found in file: {old_text[:50]}..."
                }

            if replace_all:
                new_content = content.replace(old_text, new_text)
                replacements = content.count(old_text)
            else:
                new_content = content.replace(old_text, new_text, 1)
                replacements = 1

            path.write_text(new_content, encoding=self.encoding)

            return {
                "success": True,
                "file_path": str(path),
                "replacements_made": replacements
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Error editing file: {e}"
            }
