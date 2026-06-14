from abc import ABC, abstractmethod
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class BaseTool(ABC):

    description = ""
    category = None
    permission = ToolPermission.LOW

    @property
    @abstractmethod
    def name(self):
        pass

    @abstractmethod
    def execute(self, **kwargs):
        pass