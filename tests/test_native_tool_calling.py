import pytest
from unittest.mock import patch, MagicMock


class TestBaseToolNativeSchema:

    def test_get_native_schema_empty_params(self):
        from tools.calculator_tool import CalculatorTool
        tool = CalculatorTool()
        schema = tool.get_native_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "calculator"
        assert schema["function"]["parameters"]["type"] == "object"
        assert "required" in schema["function"]["parameters"]
        assert "properties" in schema["function"]["parameters"]

    def test_get_native_schema_with_required_params(self):
        from tools.shell_tool import ShellTool
        tool = ShellTool()
        schema = tool.get_native_schema()
        assert schema["type"] == "function"
        assert schema["function"]["name"] == "shell"
        params = schema["function"]["parameters"]
        assert "command" in params["required"]
        assert "command" in params["properties"]
        assert params["properties"]["command"]["type"] == "string"
        assert "description" in params["properties"]["command"]

    def test_get_native_schema_optional_params_not_required(self):
        from tools.shell_tool import ShellTool
        tool = ShellTool()
        schema = tool.get_native_schema()
        params = schema["function"]["parameters"]
        assert "timeout" not in params["required"]
        assert "timeout" in params["properties"]

    def test_get_native_schema_preserves_description(self):
        from tools.calculator_tool import CalculatorTool
        tool = CalculatorTool()
        schema = tool.get_native_schema()
        assert schema["function"]["description"] == "Performs mathematical calculations"


class TestToolManagerNativeSchemas:

    def test_get_native_tool_schemas_returns_list(self):
        from tools.tool_manager import ToolManager
        from tools.calculator_tool import CalculatorTool
        from tools.shell_tool import ShellTool
        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        tm.register_tool(ShellTool())
        schemas = tm.get_native_tool_schemas()
        assert isinstance(schemas, list)
        assert len(schemas) == 2

    def test_get_native_tool_schemas_format(self):
        from tools.tool_manager import ToolManager
        from tools.calculator_tool import CalculatorTool
        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        schemas = tm.get_native_tool_schemas()
        assert len(schemas) == 1
        schema = schemas[0]
        assert schema["type"] == "function"
        assert "function" in schema
        assert "name" in schema["function"]
        assert "description" in schema["function"]
        assert "parameters" in schema["function"]

    def test_get_native_tool_schemas_empty(self):
        from tools.tool_manager import ToolManager
        tm = ToolManager()
        schemas = tm.get_native_tool_schemas()
        assert schemas == []


class TestAgentLoopNativeToolCalling:

    def _make_loop(self, native=True):
        from brain.agent_loop import AgentLoop
        from brain.decision_engine import DecisionEngine
        from brain.router import Router
        from llm.ollama_client import OllamaClient
        from tools.tool_manager import ToolManager
        from tools.calculator_tool import CalculatorTool
        from brain.llm_tool_router import LLMToolRouter

        mock_decision = MagicMock(spec=DecisionEngine)
        mock_router = MagicMock(spec=Router)
        mock_llm = MagicMock(spec=OllamaClient)

        tm = ToolManager()
        tm.register_tool(CalculatorTool())

        mock_llm_tool_router = MagicMock(spec=LLMToolRouter)

        loop = AgentLoop(
            decision_engine=mock_decision,
            router=mock_router,
            llm=mock_llm,
            tool_manager=tm,
            llm_tool_router=mock_llm_tool_router,
        )
        loop.native_tool_calling = native
        return loop

    def test_native_tools_for_agent_returns_schemas(self):
        loop = self._make_loop(native=True)
        tools = loop._get_native_tools_for_agent()
        assert len(tools) == 1
        assert tools[0]["type"] == "function"
        assert tools[0]["function"]["name"] == "calculator"

    def test_native_tools_disabled_returns_empty(self):
        loop = self._make_loop(native=False)
        tools = loop._get_native_tools_for_agent()
        assert tools == []

    def test_call_llm_returns_dict_with_content_and_tool_calls(self):
        loop = self._make_loop()
        from brain.agent_context import AgentContext
        ctx = AgentContext("test")
        ctx.add_user_message("test")

        with patch("brain.agent_loop.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "calculator",
                                "arguments": {"expression": "2+2"}
                            }
                        }
                    ]
                }
            }
            result = loop._call_llm(ctx)
            assert isinstance(result, dict)
            assert "content" in result
            assert "tool_calls" in result
            assert len(result["tool_calls"]) == 1
            assert result["tool_calls"][0]["name"] == "calculator"

    def test_call_llm_returns_empty_tool_calls_for_text(self):
        loop = self._make_loop()
        from brain.agent_context import AgentContext
        ctx = AgentContext("hello")
        ctx.add_user_message("hello")

        with patch("brain.agent_loop.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": "Hello there!",
                    "tool_calls": []
                }
            }
            result = loop._call_llm(ctx)
            assert result["content"] == "Hello there!"
            assert result["tool_calls"] == []

    def test_call_llm_passes_tools_to_ollama(self):
        loop = self._make_loop(native=True)
        from brain.agent_context import AgentContext
        ctx = AgentContext("test")
        ctx.add_user_message("test")

        with patch("brain.agent_loop.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {"content": "ok", "tool_calls": []}
            }
            loop._call_llm(ctx)
            call_kwargs = mock_ollama.chat.call_args[1]
            assert "tools" in call_kwargs
            assert len(call_kwargs["tools"]) == 1


class TestLLMToolRouterNative:

    def _make_router(self, native=True):
        from brain.llm_tool_router import LLMToolRouter
        from tools.tool_manager import ToolManager
        from tools.calculator_tool import CalculatorTool

        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        router = LLMToolRouter(tm)
        router.native_tool_calling = native
        return router

    def test_native_router_passes_tools(self):
        router = self._make_router(native=True)
        with patch("brain.llm_tool_router.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": "",
                    "tool_calls": [
                        {
                            "function": {
                                "name": "calculator",
                                "arguments": {"expression": "1+1"}
                            }
                        }
                    ]
                }
            }
            action, request, text = router.decide_and_route("calculate 1+1")
            from models.actions import Action
            assert action == Action.USE_TOOL
            assert request.tool_name == "calculator"

    def test_native_router_no_tool_returns_chat(self):
        router = self._make_router(native=True)
        with patch("brain.llm_tool_router.ollama") as mock_ollama:
            mock_ollama.chat.return_value = {
                "message": {
                    "content": "Hello!",
                    "tool_calls": []
                }
            }
            action, request, text = router.decide_and_route("hello")
            from models.actions import Action
            assert action == Action.CHAT
            assert text == "Hello!"
