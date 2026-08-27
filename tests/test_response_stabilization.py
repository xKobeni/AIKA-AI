from types import SimpleNamespace
from unittest.mock import Mock


def test_ollama_client_reads_and_caches_tool_capabilities():
    from llm.ollama_client import OllamaClient

    client = OllamaClient.__new__(OllamaClient)
    client.model = "qwen2.5:3b"
    client._model_capabilities = {}
    client.client = Mock()
    client.client.show.side_effect = [
        {"capabilities": ["completion", "tools"]},
        {"capabilities": ["completion"]},
    ]

    assert client.supports_tools("qwen2.5:3b") is True
    assert client.supports_tools("qwen2.5:3b") is True
    assert client.supports_tools("llama3:8b") is False
    assert client.client.show.call_count == 2


def test_tool_capable_model_selects_actions_then_smart_model_answers():
    from brain.agent_loop import AgentLoop
    from brain.model_router import ModelRouter
    from tools.calculator_tool import CalculatorTool
    from tools.tool_manager import ToolManager

    manager = ToolManager()
    manager.register_tool(CalculatorTool())
    llm = Mock()
    llm._uses_configured_client = True
    llm.supports_tools.side_effect = lambda model: model == "qwen2.5:3b"
    llm.chat.side_effect = [
        {"message": {"content": "Preliminary answer", "tool_calls": []}},
        {"message": {"content": "Smart final answer", "tool_calls": []}},
    ]
    router = Mock(spec=ModelRouter)
    router.fast = "qwen2.5:3b"
    router.select.return_value = "llama3:8b"
    loop = AgentLoop(
        Mock(),
        Mock(),
        llm,
        tool_manager=manager,
        llm_tool_router=object(),
        model_router=router,
    )
    loop.max_iterations = 2

    response = loop.run("Analyze this request carefully")

    assert response == "Smart final answer"
    first_call, second_call = llm.chat.call_args_list
    assert first_call.kwargs["model"] == "qwen2.5:3b"
    assert first_call.kwargs["tools"]
    assert second_call.kwargs["model"] == "llama3:8b"
    assert "tools" not in second_call.kwargs
    assert loop.last_model_used == "llama3:8b"


def test_completion_only_model_never_receives_native_tools_without_fallback():
    from brain.agent_context import AgentContext
    from brain.agent_loop import AgentLoop
    from tools.calculator_tool import CalculatorTool
    from tools.tool_manager import ToolManager

    manager = ToolManager()
    manager.register_tool(CalculatorTool())
    llm = Mock()
    llm._uses_configured_client = True
    llm.supports_tools.return_value = False
    llm.chat.return_value = {
        "message": {"content": "Direct completion", "tool_calls": []}
    }
    loop = AgentLoop(
        Mock(),
        Mock(),
        llm,
        tool_manager=manager,
        llm_tool_router=object(),
    )
    loop.model = "completion-only"

    result = loop._call_llm(
        AgentContext("answer directly"),
        allow_tools=True,
    )

    assert result["content"] == "Direct completion"
    assert "tools" not in llm.chat.call_args.kwargs


def test_evaluator_personality_and_thinking_prompts_route_to_chat():
    from brain.decision_engine import DecisionEngine
    from models.actions import Action

    classifier = Mock()
    engine = DecisionEngine(intent_classifier=classifier)
    prompts = [
        (
            "I've been improving AIKA all day and feel overwhelmed. "
            "Help me choose one small next step, naturally."
        ),
        (
            "That helps. Keep it short: what should I do first, and why "
            "that step instead of the others?"
        ),
        (
            "Analyze the tradeoffs between running AIKA entirely with local "
            "models and using cloud AI APIs. Compare privacy, cost, reliability, "
            "capability, and maintenance, then give a balanced recommendation "
            "for a personal assistant."
        ),
        (
            "I want AIKA to feel like a calm technical companion, not a "
            "customer-support bot. Suggest three response rules that would "
            "create that experience."
        ),
        (
            "Turn the second rule into a short before-and-after example. "
            "Keep the same personality direction."
        ),
        (
            "Now make the improved example more concise without making it "
            "cold. What did you remove, and why?"
        ),
    ]

    assert [engine.decide(prompt) for prompt in prompts] == [
        Action.CHAT
    ] * len(prompts)
    classifier.classify.assert_not_called()


def test_explicit_evaluator_research_prompt_resolves_web_search():
    from brain.tool_intent_resolver import DeterministicToolIntentResolver

    resolver = DeterministicToolIntentResolver()
    request = resolver.resolve(
        "Research three significant AI model releases or announcements from "
        "2026. Explain what changed and include the source link for every finding."
    )

    assert request.tool_name == "web_search"
    assert "three significant AI model releases" in request.parameters["query"]
    assert resolver.resolve("Research this repository") is None


def test_source_based_followup_stays_chat_and_does_not_search_again():
    from brain.decision_engine import DecisionEngine
    from handlers.chat_handler import ChatHandler
    from models.actions import Action

    prompt = (
        "Based only on the sources you just used, which development would "
        "matter most for a local personal assistant like AIKA? Explain your "
        "reasoning and mention any uncertainty."
    )
    classifier = Mock()
    engine = DecisionEngine(intent_classifier=classifier)
    handler = ChatHandler(
        Mock(),
        Mock(),
        Mock(),
        Mock(max_context_tokens=6000),
        tool_manager=Mock(),
    )

    assert engine.decide(prompt) == Action.CHAT
    assert handler._should_search_web(prompt) is False
    classifier.classify.assert_not_called()


def test_session_summary_uses_shared_execution_lock():
    from brain.brain import AikaBrain

    events = []

    class TrackingLock:
        def __enter__(self):
            events.append("enter")

        def __exit__(self, exc_type, exc, traceback):
            events.append("exit")

    brain = AikaBrain.__new__(AikaBrain)
    brain._execution_lock = TrackingLock()
    brain.conversation_repo = Mock()
    brain.conversation_repo.get_by_session.return_value = []

    brain._generate_session_summary("session-1")

    assert events == ["enter", "exit"]


def test_application_service_shares_foreground_lock_with_brain():
    from application.service import AikaService

    brain = Mock()
    brain.tool_manager = None
    service = AikaService(brain=brain)
    try:
        brain.set_execution_lock.assert_called_once_with(
            service._brain_execution_lock
        )
    finally:
        service.close(wait=True)
