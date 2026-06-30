from pathlib import Path
from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


class FileMultiEditTool(BaseTool):

    description = "Edits multiple files in a single operation"
    category = ToolCategory.FILE
    permission = ToolPermission.HIGH

    def __init__(self):
        self.encoding = settings.file_read_encoding

    @property
    def name(self):
        return "file_multi_edit"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "edits": {
                    "type": "string",
                    "required": True,
                    "description": (
                        "JSON array of edits. Each edit: "
                        '{"file_path": "...", "old_text": "...", "new_text": "..."}'
                    )
                }
            }
        }

    def execute(self, edits, root_path=None):
        import json

        if not settings.file_write_enabled:
            return {"success": False, "error": "File write is disabled"}

        if root_path is None:
            root_path = settings.file_search_root_path

        try:
            if isinstance(edits, str):
                edit_list = json.loads(edits)
            else:
                edit_list = edits
        except (json.JSONDecodeError, TypeError):
            return {"success": False, "error": "Invalid edits JSON format"}

        if not isinstance(edit_list, list):
            return {"success": False, "error": "Edits must be a JSON array"}

        root = Path(root_path).resolve()
        results = []
        all_success = True

        for edit in edit_list:
            file_path = edit.get("file_path")
            old_text = edit.get("old_text")
            new_text = edit.get("new_text")

            if not file_path or old_text is None:
                results.append({
                    "file_path": file_path or "?",
                    "success": False,
                    "error": "Missing file_path or old_text"
                })
                all_success = False
                continue

            path = (root / file_path).resolve()

            if not str(path).startswith(str(root)):
                results.append({
                    "file_path": file_path,
                    "success": False,
                    "error": "Access denied: path is outside workspace"
                })
                all_success = False
                continue

            if not path.exists():
                results.append({
                    "file_path": file_path,
                    "success": False,
                    "error": f"File not found: {file_path}"
                })
                all_success = False
                continue

            try:
                content = path.read_text(encoding=self.encoding)

                if old_text not in content:
                    results.append({
                        "file_path": file_path,
                        "success": False,
                        "error": f"Text not found in {file_path}"
                    })
                    all_success = False
                    continue

                new_content = content.replace(old_text, new_text, 1)
                path.write_text(new_content, encoding=self.encoding)

                results.append({
                    "file_path": file_path,
                    "success": True,
                    "replacements_made": 1
                })

            except Exception as e:
                results.append({
                    "file_path": file_path,
                    "success": False,
                    "error": str(e)
                })
                all_success = False

        return {
            "success": all_success,
            "results": results,
            "total_edits": len(edit_list),
            "successful": sum(1 for r in results if r["success"])
        }
