from pathlib import Path
from unittest.mock import Mock


ROOT = Path(__file__).resolve().parents[1]


def _persona_text(relative_path):
    return (ROOT / relative_path).read_text(encoding="utf-8")


def test_default_and_aika_personas_share_transparent_identity_rules():
    default_persona = _persona_text("src/config/persona.txt")
    agent_persona = _persona_text("src/config/personas/aika.txt")

    assert default_persona == agent_persona
    lowered = default_persona.lower()
    for required in (
        "you are an ai, not a human",
        "never claim consciousness",
        "never claim this is a first interaction",
        "never claim to remember information that is absent",
        "describe only capabilities actually available",
        "never claim an action was completed unless",
        "never fabricate facts",
    ):
        assert required in lowered


def test_persona_no_longer_encourages_fabricated_human_experience():
    persona = _persona_text("src/config/persona.txt").lower()

    for removed_instruction in (
        "natural and human",
        "shows genuine curiosity, humor, and emotion",
        "express genuine reactions",
        '"i feel"',
        "like a close friend",
    ):
        assert removed_instruction not in persona


def test_shared_request_context_always_includes_identity_grounding():
    from brain.request_context import RequestContext

    context = RequestContext(
        user_message="Are you there?",
        agent_id="aika",
        session_id="session-1",
        persona="Warm AIKA persona",
        current_time="10:00",
        current_date="Monday, August 24, 2026",
        memory_context="",
        conversation_context="User: Earlier message\nAIKA: Earlier answer",
        cross_session_context="",
        allowed_tools=("date_time",),
    )

    prompt = "\n\n".join(context.prompt_sections())

    assert "You are an AI, not a human" in prompt
    assert "Do not claim a first interaction when history is present" in prompt
    assert "User: Earlier message" in prompt
    assert "AIKA: Earlier answer" in prompt


def test_tool_response_prompt_requires_transparent_capability_language():
    from handlers.tool_response_handler import ToolResponseHandler

    llm = Mock()
    llm.generate.return_value = "Opened Camera."
    handler = ToolResponseHandler(llm)

    assert (
        handler.generate_response(
            "Open Camera", "app_launcher", {"success": True}
        )
        == "Opened Camera."
    )

    prompt = llm.generate.call_args.args[0]
    assert "transparent AI identity" in prompt
    assert "Do not claim feelings, personal experiences" in prompt
    assert "successful actions that the Tool Result does not confirm" in prompt


def test_tool_response_fallback_names_the_tool_without_inventing_success():
    from handlers.tool_response_handler import ToolResponseHandler

    llm = Mock()
    llm.generate.side_effect = RuntimeError("private model detail")
    handler = ToolResponseHandler(llm)

    response = handler.generate_response(
        "Search", "web_search", {"success": False, "error": "offline"}
    )

    assert response.startswith("Here is what web_search returned:")
    assert "private model detail" not in response
