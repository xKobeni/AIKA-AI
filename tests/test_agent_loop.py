import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from unittest.mock import MagicMock, patch
from brain.agent_context import AgentContext
from brain.reflection import ReflectionEngine
from brain.agent_loop import AgentLoop
from models.actions import Action


passed = 0
failed = 0


def check(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  PASS: {name}")
        passed += 1
    else:
        print(f"  FAIL: {name} {detail}")
        failed += 1


print("=== Test AgentContext ===\n")

ctx = AgentContext("research AI trends")

check(
    "original message stored",
    ctx.original_message == "research AI trends"
)

check(
    "starts with 0 iterations",
    ctx.iterations == 0
)

check(
    "starts with empty history",
    len(ctx.actions_taken) == 0
)

check(
    "is_done defaults to False",
    ctx.is_done is False
)

ctx.add_iteration(Action.USE_TOOL, "web_search", "Found 5 results about AI")

check(
    "iteration incremented",
    ctx.iterations == 1
)

check(
    "action recorded",
    len(ctx.actions_taken) == 1
)

check(
    "action has correct fields",
    ctx.actions_taken[0]["action"] == "use_tool"
    and ctx.actions_taken[0]["tool"] == "web_search"
    and "Found 5 results" in ctx.actions_taken[0]["result"]
)

check(
    "final_response updated",
    "Found 5 results" in ctx.final_response
)

ctx.add_iteration(Action.CHAT, None, "Here is a summary of AI trends...")

check(
    "second iteration tracked",
    ctx.iterations == 2
    and len(ctx.actions_taken) == 2
)

history = ctx.get_history_for_llm()

check(
    "history contains both actions",
    "use_tool" in history and "chat" in history
)

check(
    "history contains iteration numbers",
    "1." in history and "2." in history
)

check(
    "enriched input includes history on iteration 2",
    "Previous actions" in ctx.get_enriched_input("research AI trends")
)

ctx2 = AgentContext("hello")
check(
    "enriched input is plain message on iteration 0",
    ctx2.get_enriched_input("hello") == "hello"
)

check(
    "get_action_count works",
    ctx.get_action_count("use_tool") == 1
)

check(
    "get_action_count with tool filter",
    ctx.get_action_count("use_tool", "web_search") == 1
)

check(
    "get_action_count returns 0 for unmatched",
    ctx.get_action_count("use_tool", "calculator") == 0
)

ctx_fail = AgentContext("research quantum computing")
ctx_fail.add_iteration(Action.USE_TOOL, "web_search", "No search results found.")
ctx_fail.add_iteration(Action.USE_TOOL, "web_search", "Error: timeout")

check(
    "is_last_action_repeated_and_failed detects repeated failure",
    ctx_fail.is_last_action_repeated_and_failed() is True
)

ctx_fail2 = AgentContext("research quantum computing")
ctx_fail2.add_iteration(Action.USE_TOOL, "web_search", "No search results found.")
ctx_fail2.add_iteration(Action.USE_TOOL, "web_search", "Found 5 articles.")

check(
    "is_last_action_repeated_and_failed returns False if second succeeded",
    ctx_fail2.is_last_action_repeated_and_failed() is False
)

ctx_fail3 = AgentContext("research quantum computing")
ctx_fail3.add_iteration(Action.USE_TOOL, "web_search", "No search results found.")
ctx_fail3.add_iteration(Action.USE_TOOL, "file_search", "No matches found.")

check(
    "is_last_action_repeated_and_failed returns False for different actions",
    ctx_fail3.is_last_action_repeated_and_failed() is False
)

ctx_fail4 = AgentContext("research quantum computing")
check(
    "is_last_action_repeated_and_failed returns False with 0 or 1 actions",
    ctx_fail4.is_last_action_repeated_and_failed() is False
)
ctx_fail4.add_iteration(Action.USE_TOOL, "web_search", "No search results found.")
check(
    "is_last_action_repeated_and_failed returns False with 1 action",
    ctx_fail4.is_last_action_repeated_and_failed() is False
)

ctx_enrich = AgentContext("research AI")
ctx_enrich.add_iteration(Action.USE_TOOL, "web_search", "No search results found.")

enriched = ctx_enrich.get_enriched_input("research AI")

check(
    "enriched input mentions failed actions to avoid",
    "Do NOT try these actions again" in enriched
    or "use_tool" in enriched
)


print("\n=== Test ReflectionEngine ===\n")

mock_llm = MagicMock()
reflection = ReflectionEngine()

with patch.object(reflection, "model", "test_model"):
    with patch("brain.reflection.ollama") as mock_ollama:
        mock_ollama.chat.return_value = {
            "message": {"content": "DONE"}
        }
        result = reflection.reflect(
            "research AI",
            "1. web_search: Found results",
            "Here are the results..."
        )

        check(
            "returns done=True for DONE response",
            result["done"] is True
        )

        check(
            "returns next_action=None for DONE",
            result["next_action"] is None
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        mock_ollama.chat.return_value = {
            "message": {"content": "NEXT: read the first result"}
        }
        result = reflection.reflect(
            "research AI",
            "1. web_search: Found results",
            "Here are the results..."
        )

        check(
            "returns done=False for NEXT response",
            result["done"] is False
        )

        check(
            "returns next_action text",
            result["next_action"] == "read the first result"
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        mock_ollama.chat.return_value = {
            "message": {"content": "done, the task is complete"}
        }
        result = reflection.reflect(
            "hello",
            "",
            "Hello! How can I help?"
        )

        check(
            "handles case-insensitive DONE",
            result["done"] is True
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        mock_ollama.chat.side_effect = Exception("connection error")
        result = reflection.reflect(
            "test",
            "",
            "test result"
        )

        check(
            "handles LLM errors gracefully",
            result["done"] is True
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        result = reflection.reflect(
            "research AI",
            "1. web_search",
            "No search results found."
        )

        check(
            "fail-fast on 'no search results'",
            result["done"] is True
        )
        check(
            "fail-fast does not call LLM",
            mock_ollama.chat.call_count == 0
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        result = reflection.reflect(
            "research AI",
            "1. web_search",
            "Error: connection timeout"
        )

        check(
            "fail-fast on 'error'",
            result["done"] is True
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        result = reflection.reflect(
            "research AI",
            "1. web_search",
            "I couldn't find any information about that topic."
        )

        check(
            "fail-fast on 'couldn't find'",
            result["done"] is True
        )

    with patch("brain.reflection.ollama") as mock_ollama:
        result = reflection.reflect(
            "research AI",
            "1. web_search",
            "Here are 5 results about AI trends."
        )

        check(
            "normal result proceeds to LLM",
            result["done"] is False or result["done"] is True
        )
        check(
            "normal result calls LLM",
            mock_ollama.chat.call_count == 1
        )


print("\n=== Test AgentLoop ===\n")

mock_decision = MagicMock()
mock_router = MagicMock()
mock_llm = MagicMock()

mock_router.route.return_value = "Here is what I found about AI trends."

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 5
    mock_settings.agent_reflection_enabled = False

    loop = AgentLoop(mock_decision, mock_router, mock_llm)

    check(
        "max_iterations loaded from settings",
        loop.max_iterations == 5
    )

    check(
        "reflection_enabled loaded from settings",
        loop.reflection_enabled is False
    )

    mock_decision.decide.return_value = Action.CHAT
    result = loop.run("hello")

    check(
        "single iteration with reflection disabled",
        result == "Here is what I found about AI trends."
    )

    check(
        "decide was called once",
        mock_decision.decide.call_count == 1
    )

    check(
        "router was called once",
        mock_router.route.call_count == 1
    )

mock_decision.reset_mock()
mock_router.reset_mock()

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 3
    mock_settings.agent_reflection_enabled = True

    loop = AgentLoop(mock_decision, mock_router, mock_llm)

    mock_decision.decide.side_effect = [
        Action.USE_TOOL,
        Action.USE_TOOL,
        Action.CHAT
    ]
    mock_router.route.side_effect = [
        "Processing request...",
        "Still working on it...",
        "Here is a summary of the article."
    ]

    with patch.object(loop.reflection, "reflect") as mock_reflect:
        mock_reflect.side_effect = [
            {"done": False, "next_action": "read the result"},
            {"done": False, "next_action": "summarize it"},
        ]

        result = loop.run("research AI trends")

        check(
            "multi-iteration loop runs correctly",
            "summary" in result.lower() or "article" in result.lower()
        )

        check(
            "decide called 3 times",
            mock_decision.decide.call_count == 3
        )

        check(
            "router called 3 times",
            mock_router.route.call_count == 3
        )

        check(
            "reflection called 2 times (stopped before 3rd)",
            mock_reflect.call_count == 2
        )

mock_decision.reset_mock()
mock_router.reset_mock()
mock_decision.decide.side_effect = None
mock_router.route.side_effect = None

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 2
    mock_settings.agent_reflection_enabled = True

    loop = AgentLoop(mock_decision, mock_router, mock_llm)

    mock_decision.decide.side_effect = [
        Action.USE_TOOL,
        Action.USE_TOOL
    ]
    mock_router.route.side_effect = [
        "Result 1",
        "Result 2"
    ]

    with patch.object(loop.reflection, "reflect") as mock_reflect2:
        mock_reflect2.side_effect = [
            {"done": False, "next_action": "keep going"},
            {"done": False, "next_action": "still not done"}
        ]

        result = loop.run("complex task")

        check(
            "stops at max iterations",
            result == "Result 2"
        )

        check(
            "only ran max_iterations times",
            mock_decision.decide.call_count == 2
        )

mock_decision.reset_mock()
mock_router.reset_mock()
mock_decision.decide.side_effect = None
mock_router.route.side_effect = None

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 5
    mock_settings.agent_reflection_enabled = True

    loop = AgentLoop(mock_decision, mock_router, mock_llm)

    mock_decision.decide.return_value = Action.CHAT
    mock_router.route.return_value = "Hello! How can I help?"

    with patch.object(loop.reflection, "reflect") as mock_reflect3:
        result = loop.run("hi")

        check(
            "CHAT action stops loop immediately",
            result == "Hello! How can I help?"
        )

        check(
            "no reflection call for terminal action",
            mock_reflect3.call_count == 0
        )

mock_decision.reset_mock()
mock_router.reset_mock()
mock_decision.decide.side_effect = None
mock_router.route.side_effect = None

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 5
    mock_settings.agent_reflection_enabled = True

    loop = AgentLoop(mock_decision, mock_router, mock_llm)

    mock_decision.decide.side_effect = [
        Action.USE_TOOL,
        Action.USE_TOOL,
        Action.USE_TOOL
    ]
    mock_router.route.side_effect = [
        "No search results found.",
        "No search results found.",
        "This should not run"
    ]

    with patch.object(loop.reflection, "reflect") as mock_reflect4:
        mock_reflect4.side_effect = [
            {"done": False, "next_action": "try something else"},
            {"done": False, "next_action": "try again"},
        ]

        result = loop.run("research obscure topic")

        check(
            "stops after repeated failure",
            result == "No search results found."
        )
        check(
            "only ran 2 iterations (stopped on repeated failure)",
            mock_decision.decide.call_count == 2
        )
        check(
            "third iteration was NOT executed",
            mock_router.route.call_count == 2
        )

mock_decision.reset_mock()
mock_router.reset_mock()
mock_decision.decide.side_effect = None
mock_router.route.side_effect = None

print("\n=== Test Success Heuristic ===\n")

mock_decision2 = MagicMock()
mock_router2 = MagicMock()
mock_llm2 = MagicMock()

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 5
    mock_settings.agent_reflection_enabled = True

    loop = AgentLoop(mock_decision2, mock_router2, mock_llm2)

    check(
        "substantive result detected: long text with 'here are'",
        loop._is_substantive_result(
            "Here are the top 5 AI trends for 2026: "
            "1. Agentic AI, 2. Multimodal models, "
            "3. Edge computing, 4. AI safety, 5. Autonomous systems."
        ) is True
    )

    check(
        "substantive result detected: 'found' keyword",
        loop._is_substantive_result(
            "Found 10 search results about machine learning "
            "including articles from MIT and Stanford."
        ) is True
    )

    check(
        "non-substantive: too short",
        loop._is_substantive_result("ok") is False
    )

    check(
        "non-substantive: error message",
        loop._is_substantive_result(
            "No search results found for that query."
        ) is False
    )

    check(
        "non-substantive: generic short text",
        loop._is_substantive_result("Processing...") is False
    )

    check(
        "substantive: long text without keywords",
        loop._is_substantive_result(
            "The field of artificial intelligence has seen remarkable "
            "progress in recent years. Machine learning models can now "
            "understand natural language, generate images, write code, "
            "and even reason about complex problems. These advances "
            "are transforming industries from healthcare to finance."
        ) is True
    )

mock_decision2.reset_mock()
mock_router2.reset_mock()

with patch("brain.agent_loop.settings") as mock_settings:
    mock_settings.agent_max_iterations = 5
    mock_settings.agent_reflection_enabled = True

    loop = AgentLoop(mock_decision2, mock_router2, mock_llm2)

    mock_decision2.decide.side_effect = [
        Action.USE_TOOL,
        Action.USE_TOOL
    ]
    mock_router2.route.side_effect = [
        "Here are the search results for AI trends: 5 articles found.",
        "This should not run"
    ]

    with patch.object(loop.reflection, "reflect") as mock_reflect5:
        result = loop.run("research AI trends")

        check(
            "stops on substantive result without reflection",
            "search results" in result.lower()
        )
        check(
            "only 1 iteration for substantive result",
            mock_decision2.decide.call_count == 1
        )
        check(
            "reflection NOT called for substantive result",
            mock_reflect5.call_count == 0
        )


print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
