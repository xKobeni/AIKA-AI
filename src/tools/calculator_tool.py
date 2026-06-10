from tools.base_tool import BaseTool


class CalculatorTool(BaseTool):

    @property
    def name(self):

        return "calculator"

    def execute(
        self,
        expression
    ):

        try:

            return str(
                eval(expression)
            )

        except Exception as e:

            return f"Calculation error: {e}"