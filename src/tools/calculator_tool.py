import ast
import operator

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings


SAFE_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Pow: operator.pow,
    ast.Mod: operator.mod,
    ast.USub: operator.neg,
    ast.UAdd: operator.pos,
}


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

        if len(expression) > settings.max_calculation_length:
            return {
                "success": False,
                "error": "Expression too long"
            }

        try:

            tree = ast.parse(expression.strip(), mode="eval")

            result = self._eval_node(tree.body)

            return {
                "success": True,
                "result": str(result)
            }

        except Exception as e:

            return {
                "success": False,
                "error": f"Calculation error: {e}"
            }

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {
                "expression": {
                    "type": "string",
                    "required": True,
                    "description": "Mathematical expression to evaluate, e.g. '2 + 2 * 3'"
                }
            }
        }

    def _eval_node(self, node):

        if isinstance(node, ast.Constant):
            return node.value

        if isinstance(node, ast.UnaryOp):
            op = SAFE_OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(self._eval_node(node.operand))

        if isinstance(node, ast.BinOp):
            op = SAFE_OPERATORS.get(type(node.op))
            if op is None:
                raise ValueError(f"Unsupported operator: {type(node.op).__name__}")
            return op(
                self._eval_node(node.left),
                self._eval_node(node.right)
            )

        raise ValueError(f"Unsupported expression: {type(node).__name__}")