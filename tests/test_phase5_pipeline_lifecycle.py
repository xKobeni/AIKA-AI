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
