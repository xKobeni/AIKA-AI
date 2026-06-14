from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission


class CalculatorTool(BaseTool):

    description = "Performs mathematical calculations"
    category = ToolCategory.PRODUCTIVITY
    permission = ToolPermission.LOW

    @property
    def name(self):

        return "calculator"

    def execute(
        self,
        expression
    ):

        try:

            return {
                "success": True,
                "result": str(
                    eval(expression)
                )
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Calculation error: {e}"
            }