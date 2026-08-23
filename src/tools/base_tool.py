from abc import ABC, abstractmethod
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class BaseTool(ABC):

    description = ""
    category = None
    permission = ToolPermission.LOW
    response_policy = "synthesize"

    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def execute(self, **kwargs):
        pass

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {}
        }

    def get_native_schema(self):
        schema = self.get_schema()
        params = schema.get("parameters", {})
        required = [k for k, v in params.items() if v.get("required", False)]
        properties = {}
        for k, v in params.items():
            prop = {"type": v.get("type", "string")}
            if "description" in v:
                prop["description"] = v["description"]
            if "default" in v:
                prop["default"] = v["default"]
            properties[k] = prop
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "required": required,
                    "properties": properties
                }
            }
        }
