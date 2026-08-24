import logging
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock, patch


def _agent_loop():
    from brain.agent_loop import AgentLoop

    tool_manager = SimpleNamespace(tools={})
    return AgentLoop(
        decision_engine=Mock(),
        router=Mock(),
        llm=Mock(),
        tool_manager=tool_manager,
        llm_tool_router=object(),
    )


def test_agent_loop_records_empty_stream_without_logging_user_text(caplog):
    loop = _agent_loop()
    loop._run_llm_loop_stream = Mock(return_value=iter(()))

    with caplog.at_level(logging.ERROR, logger="brain.agent_loop"):
        chunks = list(loop.run_stream("private movie search request"))

    assert chunks == []
    assert loop.last_run_status == "empty_response"
    assert "status=empty_response" in caplog.text
    assert "private movie search request" not in caplog.text


def test_agent_loop_observability_records_tool_name_without_parameters():
    loop = _agent_loop()

    loop._reset_run_observability()
    loop._record_tool_execution(
        "web_search",
        {"success": True, "query": "sensitive search terms"},
    )

    assert loop.last_tool_used == "web_search"
    assert loop.last_tools_used == [{"tool": "web_search", "success": True}]


def test_agent_finalizer_persists_route_and_tool_metadata():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    brain.response_finalizer = Mock()
    brain.response_finalizer.finalize.return_value = Mock()
    brain.conversation_repo = Mock()
    brain.embedding_service = Mock()
    brain.session_repo = Mock()
    brain.current_session = SimpleNamespace(id="session-1")
    brain.current_agent_id = "aika"
    brain.llm = Mock()
    brain.llm.get_last_metrics.return_value = {}

    brain._finalize_agent_response(
        "Five movie results",
        SimpleNamespace(id=42),
        "llama3:8b",
        intent="use_tool",
        tool_used="web_search",
    )

    kwargs = brain.response_finalizer.finalize.call_args.kwargs
    assert kwargs["intent"] == "use_tool"
    assert kwargs["tool_used"] == "web_search"
    assert kwargs["model_used"] == "llama3:8b"


def _shared_request_context():
    from brain.request_context import RequestContext

    return RequestContext(
        user_message="current question",
        agent_id="aika",
        session_id="session-1",
        persona="AIKA persona",
        current_time="14:30",
        current_date="Sunday, August 23, 2026",
        memory_context="The user is building AIKA.",
        conversation_context="User: Earlier question\nAIKA: Earlier answer",
        cross_session_context="A prior project discussion.",
        allowed_tools=("calculator", "web_search"),
    )


def test_request_context_builder_captures_shared_runtime_and_agent_context():
    from brain.request_context import RequestContextBuilder

    context_manager = Mock()
    context_manager.build_context.return_value = {
        "memory_context": "Remembered preference",
        "conversation_context": "User: Hello\nAIKA: Hi",
        "cross_session_context": "Previous session summary",
    }
    registry = Mock()
    registry.get.return_value = SimpleNamespace(
        allowed_tools=["web_search", "not_registered"],
        persona_path=None,
    )
    tool_manager = SimpleNamespace(
        tools={"calculator": object(), "web_search": object()}
    )
    builder = RequestContextBuilder(
        context_manager,
        agent_registry=registry,
        tool_manager=tool_manager,
        clock=lambda: datetime(2026, 8, 23, 14, 30),
        persona_loader=lambda _agent_id: "Shared AIKA persona",
    )

    result = builder.build(
        "current question",
        session_id="session-1",
        agent_id="aika",
        query_embedding=[0.1],
    )

    assert result.current_time == "14:30"
    assert result.current_date == "Sunday, August 23, 2026"
    assert result.persona == "Shared AIKA persona"
    assert result.conversation_context == "User: Hello\nAIKA: Hi"
    assert result.allowed_tools == ("web_search",)
    context_manager.build_context.assert_called_once_with(
        "current question",
        session_id="session-1",
        agent_id="aika",
        query_embedding=[0.1],
    )


def test_context_manager_excludes_empty_assistant_history():
    from brain.context_manager import ContextManager

    conversation_repo = Mock()
    conversation_repo.get_by_session.return_value = [
        SimpleNamespace(role="user", content="Search for movies"),
        SimpleNamespace(role="assistant", content=""),
        SimpleNamespace(role="user", content="Are you there?"),
    ]
    retrieval_service = Mock()
    retrieval_service.retrieve.return_value = []
    retrieval_service.profile_builder.build_profile.return_value = ""
    manager = ContextManager(
        Mock(),
        conversation_repo,
        Mock(),
        retrieval_service=retrieval_service,
    )

    result = manager.build_context(
        "next question",
        session_id="session-1",
        agent_id="aika",
        query_embedding=[0.1],
    )

    assert result["conversation_context"] == (
        "User: Search for movies\nUser: Are you there?"
    )


def test_chat_and_agent_prompts_use_the_same_shared_context():
    from brain.agent_context import AgentContext
    from handlers.chat_handler import ChatHandler

    request_context = _shared_request_context()
    timeline = []
    builder = Mock()
    builder.build.side_effect = lambda *args, **kwargs: (
        timeline.append("context") or request_context
    )
    conversation_repo = Mock()
    conversation_repo.create.side_effect = lambda **kwargs: (
        timeline.append("persist_user") or SimpleNamespace(id=7)
    )
    llm = Mock()
    llm.generate_with_model.return_value = "answer"
    llm.get_last_metrics.return_value = {}
    finalizer = Mock()
    handler = ChatHandler(
        conversation_repo,
        llm,
        Mock(),
        Mock(),
        request_context_builder=builder,
        response_finalizer=finalizer,
    )

    with patch("handlers.chat_handler.settings") as mock_settings:
        mock_settings.max_input_length = 10_000
        mock_settings.chat_model = "model"
        result = handler.chat("current question", agent_id="aika")

    assert result == "answer"
    assert timeline[:2] == ["context", "persist_user"]
    chat_prompt = llm.generate_with_model.call_args.args[0]

    loop = _agent_loop()
    agent_prompt = loop._build_system_prompt(
        AgentContext("current question", agent_id="aika"),
        agent_id="aika",
        native=True,
        request_context=request_context,
    )

    for expected in (
        "AIKA persona",
        "Current time: 14:30",
        "Current date: Sunday, August 23, 2026",
        "User: Earlier question",
        "AIKA: Earlier answer",
        "The user is building AIKA.",
        "calculator, web_search",
    ):
        assert expected in chat_prompt
        assert expected in agent_prompt
    assert chat_prompt.count("User:\ncurrent question") == 1


def test_brain_passes_shared_context_to_streaming_agent_loop():
    from brain.brain import AikaBrain
    from models.actions import Action

    request_context = _shared_request_context()
    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = "aika"
    brain.current_session = SimpleNamespace(id="session-1")
    brain.decision_engine = Mock()
    brain.decision_engine.decide.return_value = Action.USE_TOOL
    brain.embedding_service = Mock()
    brain.embedding_service.generate_embedding.return_value = [0.1]
    brain.request_context_builder = Mock()
    brain.request_context_builder.build.return_value = request_context
    brain.conversation_repo = Mock()
    brain.conversation_repo.create.return_value = SimpleNamespace(id=9)
    brain.agent_loop = Mock()
    brain.agent_loop.run_stream.return_value = iter(("answer",))
    brain.agent_loop.last_model_used = "llama3:8b"
    brain.agent_loop.last_tool_used = "web_search"
    brain.agent_loop.last_tools_used = [
        {"tool": "web_search", "success": True}
    ]
    brain.agent_loop.last_run_status = "completed"
    brain.agent_loop.last_iterations = 2
    brain.agent_loop.last_error_type = None
    brain.response_finalizer = Mock()
    brain.response_finalizer.finalize.return_value = SimpleNamespace(
        user_conversation_id=9
    )
    brain.session_repo = Mock()
    brain.memory_extractor = Mock()
    brain._executor = Mock()
    brain._closed = False
    brain.llm = Mock()
    brain.llm.get_last_metrics.return_value = {}

    assert list(brain.process_stream("current question")) == ["answer"]

    brain.agent_loop.run_stream.assert_called_once_with(
        "current question",
        agent_id="aika",
        request_context=request_context,
        initial_tool_request=None,
    )
    assert brain.last_stream_status == "completed"
    assert brain.last_stream_error_type is None


def test_date_time_tool_uses_an_aware_host_clock():
    from tools.date_time_tool import DateTimeTool

    local_zone = timezone(timedelta(hours=8), name="PHT")
    tool = DateTimeTool(
        clock=lambda: datetime(2026, 8, 23, 14, 5, 7, tzinfo=local_zone)
    )

    result = tool.execute()

    assert result["success"] is True
    assert result["date"] == "2026-08-23"
    assert result["time"] == "14:05:07"
    assert result["utc_offset"] == "UTC+08:00"
    assert "Sunday, August 23, 2026" in result["text"]
    assert "2:05:07 PM" in result["text"]


def test_deterministic_system_request_resolution_is_conservative():
    from brain.tool_intent_resolver import DeterministicToolIntentResolver

    resolver = DeterministicToolIntentResolver()

    assert resolver.resolve("What is the date and time today?").tool_name == "date_time"
    camera = resolver.resolve("Can you open my camera?")
    assert camera.tool_name == "app_launcher"
    assert camera.parameters == {"app_name": "camera"}
    screenshot = resolver.resolve("Can you screenshot this conversation?")
    assert screenshot.tool_name == "capabilities"
    assert screenshot.parameters == {"topic": "screenshot"}
    assert resolver.resolve("What tools can you use?").tool_name == "capabilities"
    assert resolver.resolve("What tools you can do?").tool_name == "capabilities"
    assert resolver.resolve("Recommend a movie for date night") is None


def test_deterministic_tool_intents_cover_reported_calculator_and_terminal_requests():
    from brain.tool_intent_resolver import DeterministicToolIntentResolver

    resolver = DeterministicToolIntentResolver()

    calculation = resolver.resolve("2+2")
    assert calculation.tool_name == "calculator"
    assert calculation.parameters == {"expression": "2+2"}

    terminal = resolver.resolve("open terminal")
    assert terminal.tool_name == "app_launcher"
    assert terminal.parameters == {"app_name": "terminal"}

    assert resolver.resolve("open up about your day") is None


def test_deterministic_tool_intents_cover_reported_memory_and_web_searches():
    from brain.tool_intent_resolver import DeterministicToolIntentResolver

    resolver = DeterministicToolIntentResolver()

    memory = resolver.resolve("can you search the memories")
    assert memory.tool_name == "memory_search"
    assert memory.parameters["query"] == "can you search the memories"

    web = resolver.resolve(
        "can you serach the internet for the top 5 best movie this 2026"
    )
    assert web.tool_name == "web_search"
    assert web.parameters == {
        "query": "the top 5 best movie this 2026"
    }

    suffix_web = resolver.resolve(
        "search 5 best movies this 2026 in the web"
    )
    assert suffix_web.tool_name == "web_search"
    assert suffix_web.parameters == {
        "query": "5 best movies this 2026"
    }


def test_deterministic_tool_intents_cover_reported_desktop_requests():
    from brain.tool_intent_resolver import DeterministicToolIntentResolver

    resolver = DeterministicToolIntentResolver()

    folder = resolver.resolve(
        "can you search my destop and open the portfolio folder"
    )
    assert folder.tool_name == "folder"
    assert folder.parameters == {
        "path": "desktop",
        "find": "portfolio",
        "open_match": True,
    }

    blank_file = resolver.resolve(
        "in the desktop can you create a blank txt file"
    )
    assert blank_file.tool_name == "file_write"
    assert blank_file.parameters == {
        "file_path": "desktop://blank.txt",
        "content": "",
        "fail_if_exists": True,
    }

    opened_file = resolver.resolve(
        "open the created blank txt in the desktop"
    )
    assert opened_file.tool_name == "app_launcher"
    assert opened_file.parameters == {
        "app_name": "file",
        "path": "desktop://blank.txt",
    }

    assert resolver.resolve(
        "open ../secret txt in the desktop"
    ) is None


def test_calculator_policy_returns_exact_result_without_another_llm_call():
    from models.tool_request import ToolRequest
    from tools.calculator_tool import CalculatorTool

    loop, llm = _loop_with_registered_tool(CalculatorTool())

    response = loop.run(
        "2+2",
        initial_tool_request=ToolRequest("calculator", {"expression": "2+2"}),
    )

    assert response == "The answer is 4."
    assert loop.last_iterations == 1
    assert loop.last_run_status == "completed"
    llm.chat.assert_not_called()


def test_capabilities_report_registered_tools_for_current_agent_only():
    from tools.capabilities_tool import CapabilitiesTool

    calculator = SimpleNamespace(
        description="Performs calculations",
        category=SimpleNamespace(value="productivity"),
        permission=SimpleNamespace(value="low"),
    )
    shell = SimpleNamespace(
        description="Runs commands",
        category=SimpleNamespace(value="system"),
        permission=SimpleNamespace(value="high"),
    )
    manager = SimpleNamespace(tools={"calculator": calculator, "shell": shell})
    registry = Mock()
    registry.get.return_value = SimpleNamespace(allowed_tools=["calculator"])
    tool = CapabilitiesTool(
        manager,
        agent_registry=registry,
        agent_id_provider=lambda: "aika",
    )

    result = tool.execute()

    assert [item["name"] for item in result["tools"]] == ["calculator"]
    assert "calculator" in result["text"]
    assert "shell" not in result["text"]


def test_capabilities_report_screenshot_as_unavailable():
    from tools.capabilities_tool import CapabilitiesTool

    result = CapabilitiesTool(SimpleNamespace(tools={})).execute(
        topic="screenshot"
    )

    assert result["success"] is True
    assert result["available"] is False
    assert "no screenshot tool is registered" in result["text"]


def _loop_with_registered_tool(tool, *, max_iterations=1):
    from brain.agent_loop import AgentLoop
    from tools.tool_manager import ToolManager

    manager = ToolManager()
    manager._audit_log = Mock()
    manager.register_tool(tool)
    llm = Mock()
    llm._uses_configured_client = True
    loop = AgentLoop(
        decision_engine=Mock(),
        router=Mock(),
        llm=llm,
        tool_manager=manager,
        llm_tool_router=object(),
    )
    loop.max_iterations = max_iterations
    return loop, llm


def test_direct_result_policy_returns_natural_date_without_llm():
    from models.tool_request import ToolRequest
    from tools.date_time_tool import DateTimeTool

    local_zone = timezone(timedelta(hours=8), name="PHT")
    tool = DateTimeTool(
        clock=lambda: datetime(2026, 8, 23, 14, 5, 7, tzinfo=local_zone)
    )
    loop, llm = _loop_with_registered_tool(tool)

    response = loop.run(
        "What is the date and time?",
        initial_tool_request=ToolRequest("date_time", {}),
    )

    assert response.startswith("Today is Sunday, August 23, 2026")
    assert "[Tool Result:" not in response
    llm.chat.assert_not_called()


def test_app_launcher_policy_returns_action_confirmation_without_llm():
    from models.tool_request import ToolRequest
    from tools.app_launcher_tool import AppLauncherTool

    tool = AppLauncherTool()
    tool.execute = Mock(
        return_value={"success": True, "message": "Opened camera"}
    )
    loop, llm = _loop_with_registered_tool(tool)

    response = loop.run(
        "Open my camera",
        initial_tool_request=ToolRequest(
            "app_launcher", {"app_name": "camera"}
        ),
    )

    assert response == "Opened camera"
    llm.chat.assert_not_called()


def test_system_info_policy_requires_llm_synthesis():
    from models.tool_request import ToolRequest
    from tools.system_info_tool import SystemInfoTool

    tool = SystemInfoTool()
    tool.execute = Mock(
        return_value={"success": True, "text": "OS: Windows 11\nRAM: 50%"}
    )
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.return_value = {
        "message": {
            "content": "You're running Windows 11, with about half of RAM in use.",
            "tool_calls": [],
        }
    }

    response = loop.run(
        "What can you access?",
        initial_tool_request=ToolRequest("system_info", {}),
    )

    assert response.startswith("You're running Windows 11")
    assert "[Tool Result:" not in response
    llm.chat.assert_called_once()


def test_web_search_synthesizes_grounded_answer_once_without_tools():
    from models.tool_request import ToolRequest
    from tools.web_search_tool import WebSearchTool

    tool = WebSearchTool()
    tool.execute = Mock(return_value={
        "success": True,
        "results": [{
            "title": "Movie One",
            "href": "https://example.com/movie-one",
            "body": "A well-reviewed 2026 release.",
        }],
    })
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.return_value = iter([{
        "message": {
            "content": "Movie One stands out based on the returned review."
        }
    }])
    chunks = list(loop.run_stream(
        "search 5 best movies this 2026 in the web",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "best movies 2026"}
        ),
    ))

    response = "".join(chunks)
    assert "stands out" in response
    assert "https://example.com/movie-one" in response
    assert "[Tool Result:" not in response
    assert WebSearchTool.response_policy == "synthesize"
    llm.chat.assert_called_once()
    assert "tools" not in llm.chat.call_args.kwargs
    messages = llm.chat.call_args.kwargs["messages"]
    assert any(
        message.get("role") == "tool"
        and "Movie One" in message.get("content", "")
        and "https://example.com/movie-one" in message.get("content", "")
        for message in messages
    )
    assert "WEB SEARCH GROUNDING RULES" in messages[0]["content"]
    assert tool.execute.call_count == 1


def test_empty_web_synthesis_returns_linked_grounded_fallback_once():
    from models.tool_request import ToolRequest
    from tools.web_search_tool import WebSearchTool

    tool = WebSearchTool()
    tool.execute = Mock(return_value={
        "success": True,
        "results": [{
            "title": "Movie One",
            "href": "https://example.com/movie-one",
            "body": "A well-reviewed 2026 release.",
        }],
    })
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.return_value = iter([{"message": {"content": ""}}])

    response = "".join(loop.run_stream(
        "search 5 best movies this 2026 in the web",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "5 best movies this 2026"}
        ),
    ))

    assert "Here are the web search results" in response
    assert "Movie One" in response
    assert "A well-reviewed 2026 release." in response
    assert "https://example.com/movie-one" in response
    assert loop.last_run_status == "fallback_response"
    assert llm.chat.call_count == 1
    assert "tools" not in llm.chat.call_args.kwargs
    assert tool.execute.call_count == 1


def test_failed_web_synthesis_returns_linked_fallback_without_retry():
    from models.tool_request import ToolRequest
    from tools.web_search_tool import WebSearchTool

    tool = WebSearchTool()
    tool.execute = Mock(return_value={
        "success": True,
        "results": [{
            "title": "Movie One",
            "href": "https://example.com/movie-one",
            "body": "A well-reviewed 2026 release.",
        }],
    })
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.side_effect = RuntimeError("private model detail")

    response = "".join(loop.run_stream(
        "search 5 best movies this 2026 in the web",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "5 best movies this 2026"}
        ),
    ))

    assert "Movie One" in response
    assert "https://example.com/movie-one" in response
    assert "private model detail" not in response
    assert loop.last_run_status == "fallback_response"
    assert loop.last_error_type == "RuntimeError"
    assert llm.chat.call_count == 1
    assert tool.execute.call_count == 1


def test_sync_web_search_synthesizes_once_and_preserves_sources():
    from models.tool_request import ToolRequest
    from tools.web_search_tool import WebSearchTool

    tool = WebSearchTool()
    tool.execute = Mock(return_value={
        "success": True,
        "results": [{
            "title": "Movie One",
            "href": "https://example.com/movie-one",
            "body": "A well-reviewed 2026 release.",
        }],
    })
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.return_value = {
        "message": {
            "content": "Movie One is supported by the returned result.",
            "tool_calls": [],
        }
    }

    response = loop.run(
        "search 5 best movies this 2026 in the web",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "5 best movies this 2026"}
        ),
    )

    assert "supported by the returned result" in response
    assert "https://example.com/movie-one" in response
    assert llm.chat.call_count == 1
    assert "tools" not in llm.chat.call_args.kwargs
    assert tool.execute.call_count == 1


def test_empty_final_stream_retries_once_then_returns_visible_fallback():
    from models.tool_request import ToolRequest
    from tools.system_info_tool import SystemInfoTool

    tool = SystemInfoTool()
    tool.execute = Mock(return_value={"success": True, "text": "OS data"})
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.side_effect = [
        iter([{"message": {"content": "", "tool_calls": []}}]),
        {"message": {"content": "", "tool_calls": []}},
    ]

    response = "".join(loop.run_stream(
        "Inspect this system",
        initial_tool_request=ToolRequest(
            "system_info", {}
        ),
    ))

    assert response
    assert "completed the tool action" in response
    assert llm.chat.call_count == 2
    assert all(
        "tools" not in call.kwargs for call in llm.chat.call_args_list
    )


def test_stream_exception_returns_visible_fallback():
    from models.tool_request import ToolRequest
    from tools.system_info_tool import SystemInfoTool

    tool = SystemInfoTool()
    tool.execute = Mock(return_value={"success": True, "text": "OS data"})
    loop, llm = _loop_with_registered_tool(tool)
    llm.chat.side_effect = RuntimeError("local model unavailable")

    response = "".join(loop.run_stream(
        "Inspect this system",
        initial_tool_request=ToolRequest(
            "system_info", {}
        ),
    ))

    assert response
    assert "completed the tool action" in response
    assert loop.last_run_status == "llm_error"
    assert loop.last_error_type == "RuntimeError"


def test_partial_stream_exception_remains_failed_and_is_not_retried():
    from handlers.response_finalizer import STREAM_INTERRUPTION_FALLBACK
    from models.tool_request import ToolRequest
    from tools.system_info_tool import SystemInfoTool

    tool = SystemInfoTool()
    tool.execute = Mock(return_value={"success": True, "text": "OS data"})
    loop, llm = _loop_with_registered_tool(tool)

    def interrupted_stream():
        yield {"message": {"content": "Partial system answer."}}
        raise RuntimeError("private backend detail")

    llm.chat.return_value = interrupted_stream()

    response = "".join(loop.run_stream(
        "Inspect this system",
        initial_tool_request=ToolRequest("system_info", {}),
    ))

    assert response == (
        "Partial system answer.\n\n" + STREAM_INTERRUPTION_FALLBACK
    )
    assert "private backend detail" not in response
    assert loop.last_run_status == "llm_error"
    assert loop.last_error_type == "RuntimeError"
    assert llm.chat.call_count == 1


def test_recovered_tool_synthesis_does_not_append_a_second_fallback():
    from models.tool_request import ToolRequest
    from tools.system_info_tool import SystemInfoTool

    tool = SystemInfoTool()
    tool.execute = Mock(return_value={"success": True, "text": "OS data"})
    loop, llm = _loop_with_registered_tool(tool, max_iterations=3)
    llm.chat.side_effect = [
        RuntimeError("first synthesis failed"),
        iter([{"message": {"content": "The recovered answer."}}]),
    ]

    response = "".join(loop.run_stream(
        "Inspect this system",
        initial_tool_request=ToolRequest("system_info", {}),
    ))

    assert response == "The recovered answer."
    assert "couldn't generate the final response" not in response
    assert loop.last_run_status == "completed"
    assert loop.last_error_type is None


def test_memory_search_returns_only_grounded_memories_without_llm_synthesis():
    from models.tool_request import ToolRequest
    from tools.memory_search_tool import MemorySearchTool

    tool = MemorySearchTool(Mock())
    tool.execute = Mock(return_value={
        "success": True,
        "memories": ["I am building AIKA AI", "I live in the Philippines"],
    })
    loop, llm = _loop_with_registered_tool(tool)
    response = loop.run(
        "can you search the memories",
        initial_tool_request=ToolRequest(
            "memory_search", {"query": "relevant memories"}
        ),
    )

    assert "I am building AIKA AI" in response
    assert "I live in the Philippines" in response
    assert "[Tool Result:" not in response
    llm.chat.assert_not_called()


def test_file_write_confirmation_policy_returns_real_path_without_llm():
    from models.tool_request import ToolRequest
    from tools.file_write_tool import FileWriteTool

    tool = FileWriteTool()
    tool.execute = Mock(return_value={
        "success": True,
        "file_path": r"C:\Users\Adrian\Desktop\blank.txt",
        "bytes_written": 0,
    })
    loop, llm = _loop_with_registered_tool(tool)
    loop.tool_manager.set_confirmation_handler(
        lambda _tool_name, _parameters: True
    )

    response = loop.run(
        "in the desktop can you create a blank txt file",
        initial_tool_request=ToolRequest(
            "file_write",
            {
                "file_path": "desktop://blank.txt",
                "content": "",
                "fail_if_exists": True,
            },
        ),
    )

    assert response == r"Created C:\Users\Adrian\Desktop\blank.txt."
    llm.chat.assert_not_called()
