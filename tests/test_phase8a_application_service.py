from datetime import datetime, timezone
import threading
from types import SimpleNamespace
from unittest.mock import Mock


def _fake_brain(process_stream=None):
    from tools.tool_manager import ToolManager

    if process_stream is None:
        process_stream = lambda message: iter(("Hello", " world"))

    brain = SimpleNamespace()
    brain.current_agent_id = "aika"
    brain.current_session = SimpleNamespace(id="session-1")
    brain.tool_manager = ToolManager()
    brain.process_stream = process_stream
    brain.close = Mock()
    brain.llm = SimpleNamespace(
        model="test-model",
        list_models=Mock(return_value=["test-model"]),
    )
    brain.session_repo = Mock()
    brain.conversation_repo = Mock()
    brain.agent_registry = Mock()
    brain.agent_registry.get_all.return_value = []
    return brain


def test_service_stream_emits_typed_lifecycle_events():
    from application.events import AikaEventType
    from application.service import AikaService

    service = AikaService(brain=_fake_brain())
    events = list(service.stream("hello"))

    assert [event.type for event in events] == [
        AikaEventType.STATUS,
        AikaEventType.TEXT_DELTA,
        AikaEventType.TEXT_DELTA,
        AikaEventType.COMPLETED,
    ]
    assert "".join(
        event.data["text"]
        for event in events
        if event.type == AikaEventType.TEXT_DELTA
    ) == "Hello world"
    assert len({event.operation_id for event in events}) == 1
    assert events[0].to_dict()["type"] == "status"


def test_submit_collects_stream_into_result():
    from application.events import AikaEventType
    from application.service import AikaService

    service = AikaService(brain=_fake_brain())
    result = service.submit("hello")

    assert result.text == "Hello world"
    assert result.completed is True
    assert result.cancelled is False
    assert result.error is None
    assert result.events[-1].type == AikaEventType.COMPLETED


def test_high_permission_tool_approval_is_transport_neutral():
    from application.events import AikaEventType
    from application.service import AikaService
    from tools.base_tool import BaseTool
    from tools.tool_permission import ToolPermission
    from config.settings import settings

    class DangerousTool(BaseTool):
        name = "dangerous"
        permission = ToolPermission.HIGH

        def execute(self, **kwargs):
            return {"success": True, "result": "done"}

    brain = _fake_brain()
    brain.tool_manager.register_tool(DangerousTool())

    def process_stream(_message):
        result = brain.tool_manager.execute_tool(
            "dangerous", github_token="private-value", path="safe.txt"
        )
        yield "executed" if result["success"] else "rejected"

    brain.process_stream = process_stream
    service = AikaService(brain=brain)
    original = settings.tool_call_confirm_high_permission
    settings.tool_call_confirm_high_permission = True
    try:
        stream = service.stream("do it")
        status = next(stream)
        tool_request = next(stream)
        approval = next(stream)

        assert status.type == AikaEventType.STATUS
        assert tool_request.type == AikaEventType.TOOL_REQUEST
        assert approval.type == AikaEventType.APPROVAL_REQUIRED
        assert approval.data["parameters"]["github_token"] == "[REDACTED]"
        assert service.resolve_confirmation(
            approval.data["confirmation_id"], True
        ) is True

        remaining = list(stream)
    finally:
        settings.tool_call_confirm_high_permission = original

    assert any(event.type == AikaEventType.TOOL_RESULT for event in remaining)
    assert any(
        event.type == AikaEventType.TEXT_DELTA
        and event.data["text"] == "executed"
        for event in remaining
    )
    assert remaining[-1].type == AikaEventType.COMPLETED


def test_submit_rejects_unhandled_approval_instead_of_hanging():
    from application.service import AikaService
    from tools.base_tool import BaseTool
    from tools.tool_permission import ToolPermission
    from config.settings import settings

    class DangerousTool(BaseTool):
        name = "dangerous"
        permission = ToolPermission.HIGH

        def execute(self, **kwargs):
            raise AssertionError("rejected tool must not execute")

    brain = _fake_brain()
    brain.tool_manager.register_tool(DangerousTool())

    def process_stream(_message):
        result = brain.tool_manager.execute_tool("dangerous")
        yield result["error"]

    brain.process_stream = process_stream
    service = AikaService(brain=brain)
    original = settings.tool_call_confirm_high_permission
    settings.tool_call_confirm_high_permission = True
    try:
        result = service.submit("do it")
    finally:
        settings.tool_call_confirm_high_permission = original

    assert result.completed is True
    assert "cancelled" in result.text.lower()


def test_cancel_active_emits_cancelled_and_stops_followup_text():
    from application.events import AikaEventType
    from application.service import AikaService

    release = threading.Event()

    def process_stream(_message):
        yield "first"
        release.wait(2)
        yield "second"

    service = AikaService(brain=_fake_brain(process_stream))
    stream = service.stream("hello")
    assert next(stream).type == AikaEventType.STATUS
    assert next(stream).data["text"] == "first"

    assert service.cancel_active() is True
    release.set()
    remaining = list(stream)

    assert [event.type for event in remaining] == [AikaEventType.CANCELLED]
    assert service.cancel_active() is False


def test_service_exposes_bounded_session_history_and_status():
    from application.service import AikaService

    now = datetime.now(timezone.utc)
    brain = _fake_brain()
    brain.session_repo.get_all_sessions.return_value = [
        SimpleNamespace(
            id="session-1", agent_id="aika", started_at=now,
            last_active=now, message_count=2, summary="summary",
        )
    ]
    brain.conversation_repo.get_by_session.return_value = [
        SimpleNamespace(
            id=1, role="user", content="hello", tool_used=None,
            model_used=None, created_at=now, agent_id="aika",
        )
    ]
    service = AikaService(brain=brain)

    sessions = service.get_sessions(limit=1000)
    history = service.get_history(limit=1000)
    status = service.get_status(include_models=True)

    brain.session_repo.get_all_sessions.assert_called_once_with(agent_id="aika")
    brain.conversation_repo.get_by_session.assert_called_once_with(
        "session-1", limit=200, agent_id="aika"
    )
    assert sessions[0]["current"] is True
    assert history[0]["content"] == "hello"
    assert status["models"] == ["test-model"]
    assert status["active_operation_id"] is None


def test_agent_status_does_not_expose_internal_persona_paths():
    from application.service import AikaService

    brain = _fake_brain()
    brain.agent_registry.get_all.return_value = [
        SimpleNamespace(
            id="aika", name="AIKA", persona_path="private/persona.txt",
            model=None, allowed_tools=None, max_iterations=5,
            is_active=True, role="coordinator", delegates_to=[],
        )
    ]
    service = AikaService(brain=brain)

    agents = service.get_agents()

    assert agents[0]["id"] == "aika"
    assert "persona_path" not in agents[0]


def test_service_rejects_concurrent_operations():
    from application.service import AikaService

    release = threading.Event()

    def process_stream(_message):
        release.wait(2)
        yield "done"

    service = AikaService(brain=_fake_brain(process_stream))
    first = service.stream("first")
    assert next(first).data["state"] == "started"
    try:
        list(service.stream("second"))
        assert False, "concurrent request should be rejected"
    except RuntimeError as error:
        assert "already processing" in str(error)
    finally:
        service.cancel_active()
        release.set()
        list(first)


def test_service_close_is_idempotent_and_detaches_tool_handlers():
    from application.service import AikaService

    brain = _fake_brain()
    service = AikaService(brain=brain)

    service.close(wait=False)
    service.close(wait=False)

    brain.close.assert_called_once_with(wait=False)
    assert brain.tool_manager._confirmation_handler is None
    assert brain.tool_manager._event_handler is None


def test_tool_manager_direct_confirmation_fallback_remains_available():
    from tools.shell_tool import ShellTool
    from tools.tool_manager import ToolManager
    from config.settings import settings
    from unittest.mock import patch

    manager = ToolManager()
    manager.register_tool(ShellTool())
    original = settings.tool_call_confirm_high_permission
    settings.tool_call_confirm_high_permission = True
    try:
        with patch("builtins.input", return_value="n"):
            assert manager._check_confirmation("shell", {"command": "dir"}) is False
    finally:
        settings.tool_call_confirm_high_permission = original


def test_cli_consumes_service_events_and_resolves_approval(capsys):
    from application.events import AikaEvent, AikaEventType
    from application import service as service_module
    import main
    from unittest.mock import patch

    fake_service = Mock()
    fake_service.current_agent_id = "aika"
    fake_service.current_session_id = "session-1"
    fake_service.get_due_reminders.return_value = []
    fake_service.stream.return_value = iter((
        AikaEvent(
            AikaEventType.APPROVAL_REQUIRED,
            "operation-1",
            {
                "confirmation_id": "confirmation-1",
                "tool_name": "shell",
                "parameters": {"command": "dir"},
            },
        ),
        AikaEvent(
            AikaEventType.TEXT_DELTA,
            "operation-1",
            {"text": "done"},
        ),
        AikaEvent(
            AikaEventType.COMPLETED,
            "operation-1",
            {"state": "completed"},
        ),
    ))

    with patch.object(service_module, "AikaService", return_value=fake_service), patch(
        "builtins.input", side_effect=["run dir", "y", "exit"]
    ):
        main.main()

    output = capsys.readouterr().out
    assert "AIKA Online" in output
    assert "done" in output
    fake_service.resolve_confirmation.assert_called_once_with(
        "confirmation-1", True
    )
    fake_service.close.assert_called_once_with(wait=True)
    fake_service.set_reminder_handler.assert_called_once()
    fake_service.set_orchestration_handler.assert_called_once()
