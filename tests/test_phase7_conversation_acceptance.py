from datetime import datetime, timedelta, timezone
from contextlib import redirect_stdout
from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch


class InMemoryConversationRepository:
    def __init__(self):
        self.rows = []

    def create(self, role, content, session_id=None, **metadata):
        row = SimpleNamespace(
            id=len(self.rows) + 1,
            role=role,
            content=content,
            session_id=session_id,
            created_at=datetime.now(timezone.utc),
            **metadata,
        )
        self.rows.append(row)
        return row

    def get_by_session(self, session_id, limit=None, agent_id=None):
        rows = [row for row in self.rows if row.session_id == session_id]
        if agent_id is not None:
            rows = [
                row for row in rows
                if getattr(row, "agent_id", None) in {None, agent_id}
            ]
        return rows[-limit:] if limit else rows

    def trim(self, **_kwargs):
        return None


class AcceptanceContextManager:
    max_context_tokens = 6000

    def __init__(self, conversation_repo):
        self.conversation_repo = conversation_repo

    def build_context(
        self,
        _user_message,
        *,
        session_id=None,
        agent_id=None,
        query_embedding=None,
    ):
        del query_embedding
        rows = self.conversation_repo.get_by_session(
            session_id, limit=50, agent_id=agent_id
        )
        history = []
        for row in rows:
            if not str(row.content or "").strip():
                continue
            label = "User" if row.role == "user" else "AIKA"
            history.append(f"{label}: {row.content}")
        return {
            "memory_context": "",
            "conversation_context": "\n".join(history),
            "cross_session_context": "",
        }


class AcceptanceSessionRepository:
    def __init__(self):
        self.message_count = 0

    def increment_message_count(self, _session_id, amount):
        self.message_count += amount

    def update_last_active(self, _session_id):
        return None


class AcceptanceRegistry:
    def __init__(self):
        self.profile = SimpleNamespace(
            id="aika",
            name="AIKA",
            model=None,
            allowed_tools=None,
            max_iterations=2,
            persona_path=None,
            is_active=True,
        )

    def get(self, agent_id):
        return self.profile if agent_id == "aika" else None

    def get_all(self):
        return [self.profile]


class AcceptanceDecisionEngine:
    def decide(self, message):
        from models.actions import Action

        if str(message).strip().lower().startswith("search "):
            return Action.USE_TOOL
        return Action.CHAT


class ScriptedLLM:
    _uses_configured_client = True

    def __init__(self):
        from config.settings import settings

        self.model = settings.chat_model
        self.chat_calls = []
        self.chat_prompts = []

    def generate_stream(self, prompt, model=None):
        self.chat_prompts.append(prompt)
        lowered = prompt.lower().rstrip()
        if lowered.endswith("user:\nhmm aika?"):
            yield "I'm here. We were just looking at five 2026 movie results."
        elif lowered.endswith("user:\nare you there after the failed search?"):
            yield "I'm here. That last search failed, but our conversation is still intact."
        else:
            yield "Hey! I'm online and ready to help."

    def generate_with_model(self, prompt, model=None):
        return "".join(self.generate_stream(prompt, model=model))

    def chat(self, **kwargs):
        self.chat_calls.append(kwargs)
        messages = kwargs["messages"]
        if kwargs.get("stream"):
            tool_context = "\n".join(
                str(message.get("content", "")) for message in messages
            )
            if "Search provider unavailable" in tool_context:
                text = "The search provider is unavailable, so I couldn't complete that search."
            else:
                text = (
                    "Based on the returned web results, these are the five "
                    "listed 2026 movies."
                )
            return iter([{"message": {"content": text}}])

        user_message = next(
            message["content"]
            for message in messages
            if message.get("role") == "user"
        )
        return {
            "message": {
                "content": "",
                "tool_calls": [{
                    "function": {
                        "name": "web_search",
                        "arguments": {"query": user_message},
                    }
                }],
            }
        }

    def get_last_metrics(self):
        return {
            "prompt_tokens": 20,
            "response_tokens": 10,
            "response_time_ms": 5,
        }

    def close(self):
        return None


def _build_acceptance_brain():
    from agents.agent_registry import DEFAULT_AGENT_ID
    from brain.agent_loop import AgentLoop
    from brain.brain import AikaBrain
    from brain.request_context import RequestContextBuilder
    from brain.tool_intent_resolver import DeterministicToolIntentResolver
    from handlers.chat_handler import ChatHandler
    from handlers.response_finalizer import ResponseFinalizer
    from tools.app_launcher_tool import AppLauncherTool
    from tools.capabilities_tool import CapabilitiesTool
    from tools.date_time_tool import DateTimeTool
    from tools.tool_manager import ToolManager
    from tools.web_search_tool import (
        PROVIDER_UNAVAILABLE_MESSAGE,
        SEARCH_OUTCOME_PROVIDER_ERROR,
        WebSearchTool,
    )

    conversations = InMemoryConversationRepository()
    conversations.create(
        role="assistant",
        content="FOREIGN SESSION SECRET",
        session_id="other-session",
        agent_id="researcher",
    )
    sessions = AcceptanceSessionRepository()
    registry = AcceptanceRegistry()
    llm = ScriptedLLM()
    manager = ToolManager()
    manager._audit_log = Mock()

    local_zone = timezone(timedelta(hours=8), name="PHT")
    manager.register_tool(DateTimeTool(
        clock=lambda: datetime(2026, 8, 24, 10, 30, tzinfo=local_zone)
    ))
    app_launcher = AppLauncherTool()
    app_launcher.execute = Mock(
        return_value={"success": True, "message": "Opened camera"}
    )
    manager.register_tool(app_launcher)
    web_search = WebSearchTool()

    def search_result(query, **_kwargs):
        if "unavailable" in query.lower():
            return {
                "success": False,
                "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
                "results": [],
                "error": PROVIDER_UNAVAILABLE_MESSAGE,
            }
        return {
            "success": True,
            "results": [
                {
                    "title": f"Movie {index}",
                    "href": f"https://example.test/movie-{index}",
                    "body": "A 2026 movie result.",
                }
                for index in range(1, 6)
            ],
        }

    web_search.execute = Mock(side_effect=search_result)
    manager.register_tool(web_search)
    manager.register_tool(CapabilitiesTool(
        manager,
        agent_registry=registry,
        agent_id_provider=lambda: DEFAULT_AGENT_ID,
    ))

    context_manager = AcceptanceContextManager(conversations)
    request_context_builder = RequestContextBuilder(
        context_manager,
        agent_registry=registry,
        tool_manager=manager,
        clock=lambda: datetime(2026, 8, 24, 10, 30, tzinfo=local_zone),
        persona_loader=lambda _agent_id: "Transparent AIKA persona",
    )
    finalizer = ResponseFinalizer(
        conversations,
        embedding_service=None,
        session_repo=sessions,
    )
    decision_engine = AcceptanceDecisionEngine()
    agent_loop = AgentLoop(
        decision_engine,
        router=Mock(),
        llm=llm,
        tool_manager=manager,
        llm_tool_router=object(),
        model_router=None,
        agent_registry=registry,
    )
    chat_handler = ChatHandler(
        conversations,
        llm,
        Mock(),
        context_manager,
        tool_manager=manager,
        session_id="session-1",
        embedding_service=None,
        session_repo=sessions,
        model_router=None,
        agent_registry=registry,
        response_finalizer=finalizer,
        request_context_builder=request_context_builder,
    )

    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = DEFAULT_AGENT_ID
    brain.current_session = SimpleNamespace(id="session-1")
    brain.agent_registry = registry
    brain.tool_manager = manager
    brain.llm = llm
    brain.embedding_service = Mock()
    brain.embedding_service.generate_embedding.return_value = [0.1]
    brain.model_router = None
    brain.conversation_repo = conversations
    brain.session_repo = sessions
    brain.memory_extractor = Mock()
    brain._executor = Mock()
    brain._closed = False
    brain.decision_engine = decision_engine
    brain.tool_intent_resolver = DeterministicToolIntentResolver()
    brain.request_context_builder = request_context_builder
    brain.response_finalizer = finalizer
    brain.chat_handler = chat_handler
    brain.agent_loop = agent_loop
    return brain, conversations, sessions, llm, app_launcher, web_search


def test_reported_cli_conversation_replays_end_to_end_without_live_services():
    from application.service import AikaService
    from config.settings import settings

    brain, conversations, sessions, llm, app_launcher, web_search = (
        _build_acceptance_brain()
    )
    service = AikaService(brain=brain)
    inputs = [
        "sup aika how you doing",
        "well can you tell me the date and time today?",
        "well can you open my camera",
        "can you screenshot this conversation",
        "tell me what can you access and do",
        "what tools you can do?",
        "search 5 best movies this 2026 in the web",
        "hmm aika?",
        "search unavailable movie source",
        "are you there after the failed search?",
    ]

    try:
        results = [service.submit(message) for message in inputs]
    finally:
        service.close(wait=True)

    assert all(result.completed and result.error is None for result in results)
    assert all(result.text.strip() for result in results)
    assert "online" in results[0].text.lower()
    assert "Monday, August 24, 2026" in results[1].text
    assert "10:30:00 AM" in results[1].text
    assert results[2].text == "Opened camera"
    assert "no screenshot tool is registered" in results[3].text
    assert "date_time" in results[4].text
    assert "web_search" in results[5].text
    assert "Movie 1" in results[6].text
    assert "https://example.test/movie-1" in results[6].text
    assert "we were just looking" in results[7].text.lower()
    assert results[8].text == "The web-search provider is currently unavailable."
    assert "conversation is still intact" in results[9].text.lower()
    assert all("first interaction" not in result.text.lower() for result in results)

    current_rows = conversations.get_by_session(
        "session-1", agent_id="aika"
    )
    assert len(current_rows) == len(inputs) * 2
    assert [row.role for row in current_rows] == ["user", "assistant"] * len(inputs)
    assert all(str(row.content).strip() for row in current_rows)
    assert sessions.message_count == len(inputs) * 2
    assert app_launcher.execute.call_count == 1
    assert web_search.execute.call_count == 2

    assistant_by_user = {
        current_rows[index].content: current_rows[index + 1]
        for index in range(0, len(current_rows), 2)
    }
    assert assistant_by_user[inputs[0]].model_used == settings.chat_model
    assert assistant_by_user[inputs[1]].model_used is None
    assert assistant_by_user[inputs[2]].model_used is None
    assert assistant_by_user[inputs[6]].model_used == settings.chat_model
    assert assistant_by_user[inputs[7]].model_used == settings.chat_model
    assert assistant_by_user[inputs[8]].model_used == settings.chat_model

    assert llm.chat_prompts
    assert all("FOREIGN SESSION SECRET" not in prompt for prompt in llm.chat_prompts)
    final_stream_calls = [
        call for call in llm.chat_calls if call.get("stream") is True
    ]
    assert len(final_stream_calls) == 1
    assert all("tools" not in call for call in final_stream_calls)
    assert any(
        "Movie 1" in "\n".join(
            str(message.get("content", ""))
            for message in call["messages"]
        )
        for call in final_stream_calls
    )


def test_camera_unavailable_path_is_explicit_and_does_not_launch_anything():
    from tools.app_launcher_tool import AppLauncherTool

    tool = AppLauncherTool()
    with (
        patch.object(tool, "_find_executable", return_value=None),
        patch.object(tool, "_fallback_search", return_value=None),
        patch(
            "tools.app_launcher_tool.subprocess.Popen",
            side_effect=FileNotFoundError,
        ) as popen,
    ):
        result = tool.execute("camera")

    assert result["success"] is False
    assert "Could not find 'camera'" in result["error"]
    popen.assert_called_once_with(["camera"])


def test_mocked_main_cli_replays_reported_sequence_with_visible_outputs():
    import main
    from application.service import AikaService

    brain, *_rest = _build_acceptance_brain()
    service = AikaService(brain=brain)
    service.set_reminder_handler = Mock()
    service.set_orchestration_handler = Mock()
    service.get_due_reminders = Mock(return_value=[])
    inputs = [
        "sup aika how you doing",
        "well can you tell me the date and time today?",
        "well can you open my camera",
        "can you screenshot this conversation",
        "tell me what can you access and do",
        "what tools you can do?",
        "search 5 best movies this 2026 in the web",
        "hmm aika?",
        "exit",
    ]
    output = StringIO()

    with (
        patch("application.service.AikaService", return_value=service),
        patch("builtins.input", side_effect=inputs),
        redirect_stdout(output),
    ):
        main.main()

    rendered = output.getvalue()
    assert "AIKA Online" in rendered
    assert "Monday, August 24, 2026" in rendered
    assert "Opened camera" in rendered
    assert "no screenshot tool is registered" in rendered
    assert "Movie 1" in rendered
    assert "We were just looking" in rendered
    assert "first interaction" not in rendered.lower()
