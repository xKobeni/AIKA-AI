from unittest.mock import Mock, patch


def _request_context(*, conversation_context=""):
    from brain.request_context import RequestContext

    return RequestContext(
        user_message="keep the current request",
        agent_id="aika",
        session_id="session",
        persona="AIKA persona " * 300,
        current_time="19:30",
        current_date="Monday, August 24, 2026",
        memory_context="remembered detail " * 300,
        conversation_context=conversation_context,
        cross_session_context="older discussion " * 300,
        allowed_tools=("calculator",),
    )


def _agent_loop():
    from brain.agent_loop import AgentLoop

    tool_schema = {
        "type": "function",
        "function": {
            "name": "calculator",
            "description": "Evaluate a mathematical expression.",
            "parameters": {
                "type": "object",
                "properties": {
                    "expression": {"type": "string"},
                },
                "required": ["expression"],
            },
        },
    }
    tool_manager = Mock()
    tool_manager.tools = {"calculator": Mock()}
    tool_manager.get_native_tool_schemas.return_value = [tool_schema]
    tool_manager.get_schemas_json.return_value = "[calculator schema]"
    loop = AgentLoop(
        Mock(),
        Mock(),
        Mock(),
        tool_manager=tool_manager,
        llm_tool_router=Mock(),
    )
    loop.native_tool_calling = True
    return loop


def _agent_context():
    from brain.agent_context import AgentContext

    context = AgentContext("keep the current request", agent_id="aika")
    context.add_user_message("keep the current request")
    context.add_tool_call("calculator", {"expression": "1+1"})
    context.add_tool_result("calculator", "OLD-TOOL-RESULT 2")
    context.add_tool_call("calculator", {"expression": "2+2"})
    context.add_tool_result(
        "calculator",
        "LATEST-TOOL-RESULT 4 https://example.test/source",
    )
    return context


def test_small_prompt_is_unchanged_when_it_already_fits():
    from brain.prompt_budgeter import PromptBudgeter, PromptSection

    sections = [
        PromptSection("persona", "Short persona"),
        PromptSection("request", "User:\nhello", required=True, priority=100),
    ]

    assert PromptBudgeter(100).budget_text_sections(sections) == (
        "Short persona\n\nUser:\nhello"
    )


def test_dense_url_text_is_conservatively_truncated():
    from brain.prompt_budgeter import PromptBudgeter, count_tokens

    dense = "https://example.test/" + ("abcdef0123456789" * 80)
    result = PromptBudgeter.truncate_text(dense, 25)

    assert result
    assert result.startswith("https://example.test/")
    assert count_tokens(result) <= 25


def test_chat_budget_keeps_request_grounding_and_newest_history():
    from brain.prompt_budgeter import count_tokens
    from handlers.chat_handler import ChatHandler

    context_manager = Mock()
    context_manager.max_context_tokens = 120
    handler = ChatHandler(Mock(), Mock(), Mock(), context_manager)
    recent = (
        "=== RECENT CONVERSATION ===\n"
        + "OLDEST-CONTEXT\n"
        + ("middle history " * 120)
        + "\nNEWEST-CONTEXT"
    )
    sections = [
        "AIKA persona " * 100,
        "=== IDENTITY AND GROUNDING RULES ===\nNever fabricate facts.",
        recent,
        "=== INSTRUCTIONS ===\nAnswer the request directly.",
        "User:\nkeep the current request",
    ]

    prompt = handler._budget_prompt(sections)

    assert count_tokens(prompt) <= 120
    assert "Never fabricate facts" in prompt
    assert "keep the current request" in prompt
    assert "NEWEST-CONTEXT" in prompt
    assert "OLDEST-CONTEXT" not in prompt


def test_sync_agent_payload_budgets_messages_and_native_tool_schemas_together():
    from brain.prompt_budgeter import PromptBudgeter

    loop = _agent_loop()
    context = _agent_context()
    request_context = _request_context(
        conversation_context=("OLD-HISTORY " * 300) + "NEW-HISTORY"
    )

    with patch("brain.agent_loop.settings.max_context_tokens", 700), patch(
        "brain.agent_loop.ollama.chat",
        return_value={"message": {"content": "answer", "tool_calls": []}},
    ) as chat:
        loop._call_llm(context, request_context=request_context)

    kwargs = chat.call_args.kwargs
    assert PromptBudgeter.count_request(
        kwargs["messages"], kwargs.get("tools", [])
    ) <= 700
    assert any(
        message["role"] == "user"
        and message["content"] == "keep the current request"
        for message in kwargs["messages"]
    )
    assert any(
        message["role"] == "tool"
        and "LATEST-TOOL-RESULT" in message["content"]
        for message in kwargs["messages"]
    )
    assert kwargs["tools"][0]["function"]["name"] == "calculator"


def test_streaming_final_synthesis_preserves_latest_tool_result_without_tools():
    from brain.prompt_budgeter import PromptBudgeter

    loop = _agent_loop()
    context = _agent_context()
    request_context = _request_context()

    with patch("brain.agent_loop.settings.max_context_tokens", 500), patch(
        "brain.agent_loop.ollama.chat",
        return_value=iter([{"message": {"content": "grounded answer"}}]),
    ) as chat:
        result = "".join(loop._call_llm_stream(
            context,
            request_context=request_context,
            allow_tools=False,
        ))

    kwargs = chat.call_args.kwargs
    assert result == "grounded answer"
    assert "tools" not in kwargs
    assert PromptBudgeter.count_request(kwargs["messages"]) <= 500
    assert any(
        message["role"] == "tool"
        and "LATEST-TOOL-RESULT" in message["content"]
        for message in kwargs["messages"]
    )


def test_default_native_tool_registry_fits_normal_complete_prompt_budget():
    from brain.agent_context import AgentContext
    from brain.agent_loop import AgentLoop
    from brain.prompt_budgeter import PromptBudgeter
    from tools.default_tools import register_default_tools
    from tools.tool_manager import ToolManager

    tool_manager = ToolManager()
    register_default_tools(
        tool_manager,
        Mock(),
        agent_registry=Mock(),
        agent_id_provider=lambda: "aika",
    )
    loop = AgentLoop(
        Mock(),
        Mock(),
        Mock(),
        tool_manager=tool_manager,
        llm_tool_router=Mock(),
    )
    context = AgentContext("show my available tools", agent_id="aika")
    context.add_user_message("show my available tools")

    with patch("brain.agent_loop.settings.max_context_tokens", 6000):
        messages, tools = loop._prepare_llm_request(
            context,
            request_context=_request_context(),
        )

    assert len(tools) == len(tool_manager.tools)
    assert PromptBudgeter.count_request(messages, tools) <= 6000
