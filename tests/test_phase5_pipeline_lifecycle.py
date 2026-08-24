import os
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock


def test_response_finalizer_owns_persistence_metrics_and_retention():
    from handlers.response_finalizer import ResponseFinalizer

    conversation_repo = Mock()
    conversation_repo.create.return_value = SimpleNamespace(id=22)
    embedding_service = Mock()
    embedding_service.generate_embedding.return_value = [0.2] * 768
    session_repo = Mock()
    finalizer = ResponseFinalizer(
        conversation_repo,
        embedding_service=embedding_service,
        session_repo=session_repo,
    )

    metadata = finalizer.finalize(
        "answer",
        user_conversation_id=21,
        session_id="session-1",
        agent_id="agent-1",
        model_used="model-1",
        response_time_ms=15,
        prompt_tokens=10,
        response_tokens=3,
    )

    assert metadata.text == "answer"
    assert metadata.user_conversation_id == 21
    assert metadata.assistant_conversation_id == 22
    assert metadata.model_used == "model-1"
    conversation_repo.create.assert_called_once()
    session_repo.increment_message_count.assert_called_once_with("session-1", 2)
    session_repo.update_last_active.assert_called_once_with("session-1")
    conversation_repo.trim.assert_called_once_with(agent_id="agent-1")


def test_response_finalizer_never_persists_an_empty_assistant_turn():
    from handlers.response_finalizer import (
        EMPTY_RESPONSE_FALLBACK,
        ResponseFinalizer,
    )

    conversation_repo = Mock()
    conversation_repo.create.return_value = SimpleNamespace(id=22)
    embedding_service = Mock()
    session_repo = Mock()
    finalizer = ResponseFinalizer(
        conversation_repo,
        embedding_service=embedding_service,
        session_repo=session_repo,
    )

    metadata = finalizer.finalize(
        "   ",
        user_conversation_id=21,
        session_id="session-1",
        agent_id="agent-1",
        response_tokens=0,
    )

    create_kwargs = conversation_repo.create.call_args.kwargs
    assert create_kwargs["content"] == EMPTY_RESPONSE_FALLBACK
    assert create_kwargs["token_count"] > 0
    assert metadata.text == EMPTY_RESPONSE_FALLBACK
    embedding_service.generate_embedding.assert_called_once_with(
        EMPTY_RESPONSE_FALLBACK
    )


def _chat_handler_for_response(response=None, stream=None):
    from handlers.chat_handler import ChatHandler

    request_context = SimpleNamespace(
        conversation_context="",
        prompt_sections=lambda: ["AIKA persona"],
    )
    builder = Mock()
    builder.build.return_value = request_context
    conversation_repo = Mock()
    conversation_repo.create.return_value = SimpleNamespace(id=21)
    llm = Mock()
    llm.generate_with_model.return_value = response
    if stream is not None:
        llm.generate_stream.return_value = iter(stream)
    llm.get_last_metrics.return_value = {}
    finalizer = Mock()
    finalizer.finalize.return_value = SimpleNamespace(text=response)
    handler = ChatHandler(
        conversation_repo,
        llm,
        Mock(),
        SimpleNamespace(max_context_tokens=6000),
        session_id="session-1",
        response_finalizer=finalizer,
        request_context_builder=builder,
    )
    return handler, llm, finalizer


def test_sync_chat_delivers_and_finalizes_fallback_for_empty_model_output():
    from handlers.response_finalizer import EMPTY_RESPONSE_FALLBACK

    handler, _llm, finalizer = _chat_handler_for_response("   ")

    response = handler.chat("Hello", agent_id="aika")

    assert response == EMPTY_RESPONSE_FALLBACK
    assert finalizer.finalize.call_args.args[0] == EMPTY_RESPONSE_FALLBACK


def test_sync_chat_finalizes_stable_error_without_backend_details():
    from handlers.response_finalizer import GENERATION_ERROR_FALLBACK

    handler, llm, finalizer = _chat_handler_for_response()
    llm.generate_with_model.side_effect = RuntimeError(
        "private backend detail"
    )

    response = handler.chat("Hello", agent_id="aika")

    assert response == GENERATION_ERROR_FALLBACK
    assert "private backend detail" not in response
    assert finalizer.finalize.call_args.args[0] == GENERATION_ERROR_FALLBACK


def test_streaming_chat_delivers_and_finalizes_fallback_for_empty_stream():
    from handlers.response_finalizer import EMPTY_RESPONSE_FALLBACK

    handler, _llm, finalizer = _chat_handler_for_response(stream=[])

    response = "".join(handler.chat_stream("Hello", agent_id="aika"))

    assert response == EMPTY_RESPONSE_FALLBACK
    assert finalizer.finalize.call_args.args[0] == EMPTY_RESPONSE_FALLBACK


def test_streaming_chat_finalizes_stable_error_without_backend_details():
    from handlers.response_finalizer import GENERATION_ERROR_FALLBACK

    handler, llm, finalizer = _chat_handler_for_response(stream=[])
    llm.generate_stream.side_effect = RuntimeError("private backend detail")

    response = "".join(handler.chat_stream("Hello", agent_id="aika"))

    assert response == GENERATION_ERROR_FALLBACK
    assert "private backend detail" not in response
    assert finalizer.finalize.call_args.args[0] == GENERATION_ERROR_FALLBACK
    assert handler.last_run_status == "llm_error"
    assert handler.last_error_type == "RuntimeError"


def test_interrupted_chat_stream_persists_exact_visible_partial_response():
    from handlers.response_finalizer import STREAM_INTERRUPTION_FALLBACK

    handler, llm, finalizer = _chat_handler_for_response(stream=[])

    def interrupted_stream():
        yield "The first part of the answer."
        raise RuntimeError("private backend detail")

    llm.generate_stream.return_value = interrupted_stream()

    response = "".join(handler.chat_stream("Hello", agent_id="aika"))
    expected = (
        "The first part of the answer.\n\n"
        + STREAM_INTERRUPTION_FALLBACK
    )

    assert response == expected
    assert "private backend detail" not in response
    assert handler.last_run_status == "llm_error"
    assert handler.last_error_type == "RuntimeError"
    assert finalizer.finalize.call_args.args[0] == expected


def test_brain_stream_boundary_delivers_fallback_before_finalizing():
    from brain.brain import AikaBrain
    from handlers.response_finalizer import EMPTY_RESPONSE_FALLBACK
    from models.actions import Action

    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = "aika"
    brain.current_session = SimpleNamespace(id="session-1")
    brain.tool_intent_resolver = Mock()
    brain.tool_intent_resolver.resolve.return_value = None
    brain.decision_engine = Mock()
    brain.decision_engine.decide.return_value = Action.USE_TOOL
    brain.embedding_service = Mock()
    brain.embedding_service.generate_embedding.return_value = [0.1]
    brain.request_context_builder = Mock()
    brain.request_context_builder.build.return_value = SimpleNamespace()
    brain.conversation_repo = Mock()
    brain.conversation_repo.create.return_value = SimpleNamespace(id=21)
    brain.agent_loop = Mock()
    brain.agent_loop.run_stream.return_value = iter(())
    brain.agent_loop.last_model_used = "model-1"
    brain.agent_loop.last_tool_used = "web_search"
    brain.agent_loop.last_tools_used = [
        {"tool": "web_search", "success": True}
    ]
    brain.agent_loop.last_run_status = "empty_response"
    brain.agent_loop.last_iterations = 1
    brain.agent_loop.last_error_type = None
    brain.response_finalizer = Mock()
    brain.response_finalizer.finalize.side_effect = (
        lambda response, **_kwargs: SimpleNamespace(
            text=response,
            user_conversation_id=21,
        )
    )
    brain.session_repo = Mock()
    brain.memory_extractor = Mock()
    brain._executor = Mock()
    brain._closed = False
    brain.llm = Mock()
    brain.llm.get_last_metrics.return_value = {}

    response = "".join(brain.process_stream("Search the web"))

    assert response == EMPTY_RESPONSE_FALLBACK
    assert (
        brain.response_finalizer.finalize.call_args.args[0]
        == EMPTY_RESPONSE_FALLBACK
    )


def test_chat_handler_uses_injected_shared_finalizer():
    from handlers.chat_handler import ChatHandler

    finalizer = Mock()
    handler = ChatHandler(
        Mock(), Mock(), Mock(), Mock(), response_finalizer=finalizer
    )
    assert handler.response_finalizer is finalizer


def test_brain_close_is_idempotent_and_closes_background_resources():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    brain._closed = False
    brain._executor = Mock()
    brain.embedding_service = Mock()
    brain.llm = Mock()

    brain.close(wait=False)
    brain.close(wait=False)

    brain._executor.shutdown.assert_called_once_with(
        wait=False, cancel_futures=True
    )
    brain.embedding_service.close.assert_called_once_with()
    brain.llm.close.assert_called_once_with()


def test_closed_brain_does_not_submit_new_background_work():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    brain._closed = True
    brain._executor = Mock()
    brain.memory_extractor = Mock()
    brain.current_agent_id = "agent"

    brain._schedule_memory_extraction("message", 4)
    brain._executor.submit.assert_not_called()


def test_importing_main_does_not_construct_brain():
    import main

    assert callable(main.main)
    assert "brain" not in vars(main)


def test_brain_package_does_not_eagerly_import_composition_root():
    command = [
        sys.executable,
        "-c",
        "import sys, brain; print('brain.brain' in sys.modules)",
    ]
    env = os.environ.copy()
    src_dir = str(Path(__file__).resolve().parents[1] / "src")
    env["PYTHONPATH"] = os.pathsep.join(
        part for part in (src_dir, env.get("PYTHONPATH")) if part
    )
    result = subprocess.run(
        command, capture_output=True, text=True, check=True, env=env
    )
    assert result.stdout.strip() == "False"
