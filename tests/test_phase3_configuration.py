from types import SimpleNamespace
from unittest.mock import MagicMock, Mock, patch


def test_config_casts_booleans_strictly():
    from handlers.config_handler import ConfigHandler

    handler = ConfigHandler()
    assert handler._cast("false", "bool") is False
    assert handler._cast("NO", "bool") is False
    assert handler._cast("1", "bool") is True
    assert handler._cast("maybe", "bool") is None


def test_config_casts_trimmed_lists():
    from handlers.config_handler import ConfigHandler

    assert ConfigHandler()._cast("one, two, ,three", "list") == [
        "one", "two", "three"
    ]


def test_config_serializes_runtime_types_for_dotenv_roundtrip():
    from handlers.config_handler import ConfigHandler

    handler = ConfigHandler()
    assert handler._serialize_env_value(False) == "false"
    assert handler._serialize_env_value(True) == "true"
    assert handler._serialize_env_value(["one", "two"]) == "one,two"


def test_set_boolean_changes_real_type_and_notifies_refresh():
    from handlers.config_handler import ConfigHandler

    refresh = Mock()
    with patch("handlers.config_handler.settings") as mock_settings:
        mock_settings.shell_enabled = True
        handler = ConfigHandler(refresh_callback=refresh)
        result = handler._set_value("shell_enabled=false")

    assert "True to False" in result
    assert mock_settings.shell_enabled is False
    refresh.assert_called_once_with(changed_keys={"shell_enabled"})


def test_invalid_boolean_does_not_change_setting_or_refresh():
    from handlers.config_handler import ConfigHandler

    refresh = Mock()
    with patch("handlers.config_handler.settings") as mock_settings:
        mock_settings.shell_enabled = True
        handler = ConfigHandler(refresh_callback=refresh)
        result = handler._set_value("shell_enabled=maybe")

    assert "Cannot parse" in result
    assert mock_settings.shell_enabled is True
    refresh.assert_not_called()


def test_background_executor_settings_require_restart():
    from handlers.config_handler import ConfigHandler

    refresh = Mock()
    with patch("handlers.config_handler.settings") as mock_settings:
        mock_settings.background_max_workers = 1
        result = ConfigHandler(refresh_callback=refresh)._set_value(
            "background_max_workers=2"
        )

    assert "restart AIKA" in result
    assert mock_settings.background_max_workers == 2
    refresh.assert_not_called()


def test_high_impact_numeric_setting_rejects_nonpositive_value():
    from handlers.config_handler import ConfigHandler

    with patch("handlers.config_handler.settings") as mock_settings:
        mock_settings.llm_timeout = 30
        result = ConfigHandler()._set_value("llm_timeout=0")

    assert result == "llm_timeout must be greater than zero."
    assert mock_settings.llm_timeout == 30


def test_reload_notifies_existing_services():
    from handlers.config_handler import ConfigHandler

    refresh = Mock()
    with patch("handlers.config_handler.settings") as mock_settings:
        result = ConfigHandler(refresh_callback=refresh).handle("!reload")

    assert result == "Settings reloaded from environment."
    mock_settings.reload.assert_called_once_with()
    refresh.assert_called_once_with(changed_keys=None)


def test_explicit_agent_model_wins_over_smart_routing():
    from brain.model_router import ModelRouter

    with patch("brain.model_router.settings") as mock_settings:
        mock_settings.fast_model = "fast-model"
        mock_settings.smart_model = "smart-model"
        router = ModelRouter()

    model, reason = router.select_with_reason(
        "analyze and refactor this entire project",
        explicit_model="agent-model",
    )

    assert model == "agent-model"
    assert reason == "explicit_agent_model"
    assert router.last_selected == "agent-model"


def test_router_still_selects_smart_without_agent_override():
    from brain.model_router import ModelRouter

    with patch("brain.model_router.settings") as mock_settings:
        mock_settings.fast_model = "fast-model"
        mock_settings.smart_model = "smart-model"
        router = ModelRouter()

    assert router.select("analyze this") == "smart-model"
    assert router.last_reason == "smart_complex_keyword"


def test_chat_persists_the_model_actually_used():
    from handlers.chat_handler import ChatHandler

    conversation_repo = Mock()
    conversation_repo.create.side_effect = [Mock(id=12), Mock(id=13)]
    context_manager = Mock()
    context_manager.build_context.return_value = {
        "memory_context": "",
        "conversation_context": "",
        "cross_session_context": "",
    }
    llm = Mock()
    llm.generate_with_model.return_value = "response"
    model_router = Mock()
    model_router.select.return_value = "agent-model"
    registry = Mock()
    registry.get.return_value = Mock(
        model="agent-model", persona_path=None, allowed_tools=None
    )
    handler = ChatHandler(
        conversation_repo,
        llm,
        Mock(),
        context_manager,
        model_router=model_router,
        agent_registry=registry,
    )

    with patch("handlers.chat_handler.settings") as mock_settings:
        mock_settings.max_input_length = 10_000
        mock_settings.chat_model = "default-model"
        mock_settings.load_persona.return_value = "persona"
        result = handler.chat("analyze this", agent_id="researcher")

    assert result == "response"
    llm.generate_with_model.assert_called_once()
    assert llm.generate_with_model.call_args.kwargs["model"] == "agent-model"
    assistant_call = conversation_repo.create.call_args_list[1]
    assert assistant_call.kwargs["model_used"] == "agent-model"


def test_ollama_refresh_applies_host_model_and_timeout():
    from llm.ollama_client import OllamaClient

    with patch("llm.ollama_client.ollama.Client") as client_class, patch(
        "llm.ollama_client.settings"
    ) as mock_settings:
        mock_settings.chat_model = "new-chat"
        mock_settings.ollama_host = "http://ollama.internal:11434"
        mock_settings.llm_timeout = 47
        service = OllamaClient()

    client_class.assert_called_once_with(
        host="http://ollama.internal:11434", timeout=47
    )
    assert service.model == "new-chat"
    assert service.host == "http://ollama.internal:11434"
    assert service.timeout == 47


def test_embedding_refresh_applies_model_host_and_timeout():
    from llm.embedding_service import EmbeddingService

    with patch("llm.embedding_service.ollama.Client") as client_class, patch(
        "llm.embedding_service.settings"
    ) as mock_settings:
        mock_settings.embedding_model = "new-embedding"
        mock_settings.embedding_dimension = 768
        mock_settings.ollama_host = "http://ollama.internal:11434"
        mock_settings.llm_timeout = 19
        service = EmbeddingService()

    client_class.assert_called_once_with(
        host="http://ollama.internal:11434", timeout=19
    )
    assert service.model == "new-embedding"
    assert service.timeout == 19


def test_model_router_refreshes_existing_instance():
    from brain.model_router import ModelRouter

    with patch("brain.model_router.settings") as mock_settings:
        mock_settings.fast_model = "old-fast"
        mock_settings.smart_model = "old-smart"
        router = ModelRouter()
        mock_settings.fast_model = "new-fast"
        mock_settings.smart_model = "new-smart"
        router.refresh_from_settings()

    assert router.fast == "new-fast"
    assert router.smart == "new-smart"


def test_model_router_refreshes_configurable_performance_thresholds():
    from brain.model_router import ModelRouter

    with patch("brain.model_router.settings") as mock_settings:
        mock_settings.fast_model = "fast"
        mock_settings.smart_model = "smart"
        mock_settings.model_router_long_message_words = 4
        mock_settings.model_router_complex_question_words = 3
        mock_settings.model_router_escalation_iteration = 5
        mock_settings.model_router_complex_keywords = ["deep audit"]
        mock_settings.model_router_tool_heavy_prefixes = ["scan then"]
        router = ModelRouter()

    assert router.select("one two three four five") == "smart"
    assert router.select("is this question complex?") == "smart"
    assert router.select("deep audit please") == "smart"
    assert router.select("scan then summarize") == "smart"
    assert router.select("hello", iteration=4) == "fast"
    assert router.select("hello", iteration=5) == "smart"


def test_brain_refreshes_existing_components_and_registered_tools():
    from brain.brain import AikaBrain

    brain = AikaBrain.__new__(AikaBrain)
    component_names = (
        "llm", "embedding_service", "model_router", "conversation_repo",
        "context_manager", "memory_handler", "memory_extractor",
        "chat_handler", "llm_tool_router", "intent_classifier", "planner",
        "executor", "tool_handler", "agent_loop",
    )
    for name in component_names:
        setattr(brain, name, Mock())
    registered_tool = Mock()
    brain.tool_manager = SimpleNamespace(tools={"example": registered_tool})

    with patch("brain.brain.settings") as mock_settings:
        mock_settings.log_level = "INFO"
        brain._refresh_from_settings(changed_keys={"chat_model"})

    for name in component_names:
        getattr(brain, name).refresh_from_settings.assert_called_once_with()
    registered_tool.refresh_from_settings.assert_called_once_with()


def test_non_chat_persistence_uses_agent_loops_actual_model():
    from brain.brain import AikaBrain
    from models.actions import Action

    brain = AikaBrain.__new__(AikaBrain)
    brain.current_agent_id = "agent-a"
    brain.current_session = SimpleNamespace(id="session-a")
    brain.decision_engine = Mock()
    brain.decision_engine.decide.return_value = Action.USE_TOOL
    brain.embedding_service = Mock()
    brain.embedding_service.generate_embedding.return_value = [0.1] * 768
    brain.conversation_repo = Mock()
    brain.conversation_repo.create.side_effect = [
        SimpleNamespace(id=1), SimpleNamespace(id=2)
    ]
    brain.agent_loop = Mock()
    brain.agent_loop.run.return_value = "result"
    brain.agent_loop.last_model_used = "actual-agent-model"
    brain.session_repo = Mock()
    brain.memory_extractor = Mock()
    brain._executor = Mock()

    assert brain.process("calculate something") == "result"
    assistant_call = brain.conversation_repo.create.call_args_list[1]
    assert assistant_call.kwargs["model_used"] == "actual-agent-model"
