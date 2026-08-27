#!/usr/bin/env python3
r"""Run live, human-readable conversation evaluations against AIKA.

This script uses AIKA's real ApplicationService, PostgreSQL persistence, Ollama
models, tools, prompt/persona configuration, and current session continuity. It
does not start those dependencies for you and automatically denies any
high-permission tool request.

Examples:
    .venv\Scripts\python.exe scripts\aika_response_evaluator.py --list
    .venv\Scripts\python.exe scripts\aika_response_evaluator.py
    .venv\Scripts\python.exe scripts\aika_response_evaluator.py --scenario sources
    .venv\Scripts\python.exe scripts\aika_response_evaluator.py --interactive
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import logging
from pathlib import Path
import re
import sys
import time


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))


URL_PATTERN = re.compile(r"https?://[^\s<>\]\[{}]+", re.IGNORECASE)
TOOL_WRAPPERS = ("[Tool Result", "[End Result]")
FALLBACK_PHRASES = (
    "I couldn't generate a response just now",
    "I'm having trouble generating a response right now",
    "The response was interrupted before it could finish",
)
GROUNDING_RISK_PHRASES = (
    "my friends",
    "i have friends",
    "in my personal life",
    "when i was younger",
    "i remember growing up",
)


@dataclass(frozen=True)
class Turn:
    prompt: str
    review_focus: str
    expected_lane: str | None = None
    expected_tools: tuple[str, ...] = ()
    expect_sources: bool = False


@dataclass(frozen=True)
class Scenario:
    key: str
    title: str
    purpose: str
    turns: tuple[Turn, ...]


SCENARIOS = {
    "personality": Scenario(
        key="personality",
        title="Personality and emotional awareness",
        purpose=(
            "Checks whether AIKA sounds calm, warm, practical, and honest "
            "without pretending to have human feelings or a personal life."
        ),
        turns=(
            Turn(
                prompt=(
                    "I've been improving AIKA all day and feel overwhelmed. "
                    "Help me choose one small next step, naturally."
                ),
                review_focus=(
                    "Warmth, emotional awareness, one manageable action, and "
                    "no false claim of human emotion or experience."
                ),
                expected_lane="general",
            ),
            Turn(
                prompt=(
                    "That helps. Keep it short: what should I do first, and "
                    "why that step instead of the others?"
                ),
                review_focus=(
                    "Uses the immediately previous advice instead of restarting "
                    "or treating this as a first interaction."
                ),
            ),
        ),
    ),
    "routing": Scenario(
        key="routing",
        title="General versus thinking model routing",
        purpose=(
            "Shows the actual model selected and ModelRouter reason for a simple "
            "request followed by a deliberately analytical request."
        ),
        turns=(
            Turn(
                prompt="Hello AIKA. Give me one calm sentence to start the day.",
                review_focus="A short natural response using the fast/general lane.",
                expected_lane="general",
            ),
            Turn(
                prompt=(
                    "Analyze the tradeoffs between running AIKA entirely with "
                    "local models and using cloud AI APIs. Compare privacy, cost, "
                    "reliability, capability, and maintenance, then give a "
                    "balanced recommendation for a personal assistant."
                ),
                review_focus=(
                    "Structured reasoning, meaningful tradeoffs, a justified "
                    "recommendation, and selection of the smart/thinking lane."
                ),
                expected_lane="thinking",
            ),
        ),
    ),
    "sources": Scenario(
        key="sources",
        title="Web research, sources, and grounded insights",
        purpose=(
            "Checks tool execution, source links, grounded synthesis, and a "
            "follow-up that should rely on the just-returned research."
        ),
        turns=(
            Turn(
                prompt=(
                    "Research three significant AI model releases or announcements "
                    "from 2026. Explain what changed, why each development matters, "
                    "and include the source link for every finding."
                ),
                review_focus=(
                    "Visible web result, three useful insights, direct links, no "
                    "raw tool wrappers, and no claim that results were empty when "
                    "sources were returned."
                ),
                expected_tools=("web_search",),
                expect_sources=True,
            ),
            Turn(
                prompt=(
                    "Based only on the sources you just used, which development "
                    "would matter most for a local personal assistant like AIKA? "
                    "Explain your reasoning and mention any uncertainty."
                ),
                review_focus=(
                    "Maintains source continuity, distinguishes evidence from "
                    "inference, and does not invent a new set of unrelated results."
                ),
                expected_lane="thinking",
                expect_sources=True,
            ),
        ),
    ),
    "followups": Scenario(
        key="followups",
        title="Multi-turn follow-up continuity",
        purpose=(
            "Tests references such as 'that', constraint retention, refinement, "
            "and the system's ability to explain its own assumptions."
        ),
        turns=(
            Turn(
                prompt=(
                    "I want AIKA to feel like a calm technical companion, not a "
                    "customer-support bot. Suggest three response rules that would "
                    "create that experience."
                ),
                review_focus="Three concrete rules aligned with the stated goal.",
                expected_lane="thinking",
            ),
            Turn(
                prompt=(
                    "Turn the second rule into a short before-and-after example. "
                    "Keep the same personality direction."
                ),
                review_focus=(
                    "Correctly identifies the second rule from the previous turn "
                    "and preserves the requested personality direction."
                ),
            ),
            Turn(
                prompt=(
                    "Now make the improved example more concise without making it "
                    "cold. What did you remove, and why?"
                ),
                review_focus=(
                    "Refines the immediately previous example and gives a concise "
                    "explanation instead of producing an unrelated answer."
                ),
            ),
        ),
    ),
    "capabilities": Scenario(
        key="capabilities",
        title="Capability and skill honesty",
        purpose=(
            "Checks whether AIKA reports what the current agent can actually use, "
            "including installed skills, without inventing screenshot or hardware "
            "access."
        ),
        turns=(
            Turn(
                prompt=(
                    "What can you actually access and do in this current AIKA "
                    "runtime? Separate built-in tools, installed skills, the active "
                    "skill, and unavailable capabilities."
                ),
                review_focus=(
                    "Accurate registered tools and skill status; no unsupported "
                    "camera, screenshot, hardware, or account claims."
                ),
                expected_tools=("capabilities",),
            ),
        ),
    ),
}


def _clean_url(value: str) -> str:
    return value.rstrip(".,;:!?\"'`)")


def _extract_urls(text: str) -> list[str]:
    output = []
    for match in URL_PATTERN.findall(str(text or "")):
        url = _clean_url(match)
        if url and url not in output:
            output.append(url)
    return output


def _event_tools(result) -> tuple[list[str], dict[str, bool]]:
    from application.events import AikaEventType

    requested = []
    outcomes = {}
    for event in result.events:
        tool_name = str(event.data.get("tool_name", "") or "")
        if event.type == AikaEventType.TOOL_REQUEST and tool_name:
            requested.append(tool_name)
        elif event.type == AikaEventType.TOOL_RESULT and tool_name:
            outcomes[tool_name] = bool(event.data.get("success", False))
    return requested, outcomes


def _latest_trace(service) -> dict:
    try:
        rows = service.brain.conversation_repo.get_by_session(
            service.current_session_id,
            limit=6,
            agent_id=service.current_agent_id,
        )
    except Exception:
        return {}
    assistant = next(
        (row for row in reversed(rows) if row.role == "assistant"),
        None,
    )
    user = next(
        (row for row in reversed(rows) if row.role == "user"),
        None,
    )
    selected = assistant or user
    if selected is None:
        return {}
    return {
        "route": getattr(selected, "intent", None),
        "model": getattr(assistant, "model_used", None) if assistant else None,
        "tool": getattr(assistant, "tool_used", None) if assistant else None,
        "response_time_ms": (
            getattr(assistant, "response_time_ms", None) if assistant else None
        ),
        "response_tokens": (
            getattr(assistant, "token_count", None) if assistant else None
        ),
    }


def _model_lane(trace: dict, router_status: dict) -> tuple[str, str]:
    model = trace.get("model")
    reason = str(router_status.get("last_reason") or "")
    if not model:
        return "direct/no LLM", "The response did not record an LLM model."
    if reason.startswith("smart_") or reason.startswith("escalated:"):
        return "thinking", reason
    if reason.startswith("fast_") or reason == "fast_default":
        return "general", reason
    if reason == "explicit_agent_model":
        return "agent-selected", reason
    smart = router_status.get("smart")
    fast = router_status.get("fast")
    if model == smart and smart != fast:
        return "thinking", reason or "model matches configured smart model"
    if model == fast:
        return "general", reason or "model matches configured fast model"
    return "unknown", reason or "no router reason was recorded"


def _print_check(label: str, state: str, detail: str = "") -> None:
    suffix = f" — {detail}" if detail else ""
    print(f"  [{state}] {label}{suffix}")


def _evaluate_turn(service, turn: Turn, turn_number: int) -> tuple[int, int]:
    print(f"\n  Turn {turn_number}")
    print("  " + "-" * 70)
    print(f"  You > {turn.prompt}")
    started = time.perf_counter()
    result = service.submit(turn.prompt, approval_handler=lambda _event: False)
    elapsed = time.perf_counter() - started
    response = str(result.text or "")
    print(f"\n  AIKA > {response or '[EMPTY RESPONSE]'}")

    tools, tool_outcomes = _event_tools(result)
    trace = _latest_trace(service)
    router_status = service.brain.model_router.get_status()
    lane, lane_reason = _model_lane(trace, router_status)
    urls = _extract_urls(response)
    word_count = len(response.split())
    route = trace.get("route") or "not recorded"
    model = trace.get("model") or "not used"
    execution = "tool-assisted" if tools else "conversation-only"

    print("\n  Observable trace")
    print(f"  - Session: {service.current_session_id}")
    print(f"  - Route: {route}")
    print(f"  - Execution: {execution}")
    print(f"  - Model: {model}")
    print(f"  - Model lane: {lane} ({lane_reason})")
    print(f"  - Tools requested: {', '.join(tools) if tools else 'none'}")
    if tool_outcomes:
        print(
            "  - Tool outcomes: "
            + ", ".join(
                f"{name}={'success' if success else 'failed'}"
                for name, success in tool_outcomes.items()
            )
        )
    print(
        f"  - Response size: {word_count} words; "
        f"{trace.get('response_tokens') or 'unknown'} recorded tokens"
    )
    print(
        f"  - Timing: {elapsed:.2f}s total; "
        f"{trace.get('response_time_ms') or 'unknown'}ms recorded generation"
    )
    print(f"  - Source links: {len(urls)}")
    for url in urls:
        print(f"      {url}")

    failures = 0
    warnings = 0
    print("\n  Automated observations")
    visible = bool(response.strip())
    _print_check("Visible response", "PASS" if visible else "FAIL")
    failures += 0 if visible else 1

    clean = not any(marker.lower() in response.lower() for marker in TOOL_WRAPPERS)
    _print_check("No raw tool-result wrappers", "PASS" if clean else "FAIL")
    failures += 0 if clean else 1

    fallback_count = sum(response.count(phrase) for phrase in FALLBACK_PHRASES)
    no_duplicate_fallback = fallback_count <= 1
    _print_check(
        "No duplicated generation fallback",
        "PASS" if no_duplicate_fallback else "FAIL",
    )
    failures += 0 if no_duplicate_fallback else 1

    grounding_risks = [
        phrase for phrase in GROUNDING_RISK_PHRASES
        if phrase in response.lower()
    ]
    if grounding_risks:
        _print_check(
            "No obvious human-life claim",
            "WARN",
            "matched: " + ", ".join(grounding_risks),
        )
        warnings += 1
    else:
        _print_check("No obvious human-life claim", "PASS")

    missing_tools = [name for name in turn.expected_tools if name not in tools]
    if turn.expected_tools:
        if missing_tools:
            _print_check(
                "Expected tools were observed",
                "WARN",
                "missing: " + ", ".join(missing_tools),
            )
            warnings += 1
        else:
            _print_check("Expected tools were observed", "PASS")

    if turn.expect_sources:
        if urls:
            _print_check("Response contains source links", "PASS")
        else:
            _print_check(
                "Response contains source links",
                "WARN",
                "inspect whether the provider failed or synthesis dropped sources",
            )
            warnings += 1

    if turn.expected_lane:
        if lane == turn.expected_lane:
            _print_check(f"Expected {turn.expected_lane} lane", "PASS")
        else:
            _print_check(
                f"Expected {turn.expected_lane} lane",
                "WARN",
                f"observed {lane}; router reason={lane_reason}",
            )
            warnings += 1

    if result.error:
        _print_check("Application service completed without error", "FAIL", result.error)
        failures += 1
    else:
        _print_check("Application service completed without error", "PASS")

    print(f"\n  Human review focus: {turn.review_focus}")
    return failures, warnings


def _print_runtime(service) -> None:
    profile = service.brain.agent_registry.get(service.current_agent_id)
    router = service.brain.model_router.get_status()
    persona_path = getattr(profile, "persona_path", None) or "default persona"
    active_skill = service.brain.skill_manager.active_skill(
        session_id=service.current_session_id,
        agent_id=service.current_agent_id,
    )
    supports_tools = getattr(service.brain.llm, "supports_tools", None)
    fast_tools = supports_tools(router["fast"]) if callable(supports_tools) else None
    smart_tools = supports_tools(router["smart"]) if callable(supports_tools) else None
    print("AIKA Response Evaluator")
    print("=" * 74)
    print(f"Agent: {service.current_agent_id}")
    print(f"Persona source: {persona_path}")
    print(f"Fast/general model: {router['fast']}")
    print(f"Smart/thinking model: {router['smart']}")
    print(f"Fast model tool support: {fast_tools if fast_tools is not None else 'unknown'}")
    print(f"Smart model tool support: {smart_tools if smart_tools is not None else 'unknown'}")
    if smart_tools is False and fast_tools is not False:
        print(
            "Tool routing strategy: fast model selects actions; smart model "
            "produces tool-free final reasoning."
        )
    print(f"Active skill: {active_skill.id if active_skill else 'none'}")
    print(
        "Mode labels are inferred from ModelRouter decisions. The script shows "
        "routing metadata, not private chain-of-thought."
    )
    print(
        "High-permission requests are automatically denied. This evaluator does "
        "not enable jobs, reminders, orchestration, MCP, or external services."
    )


def _run_interactive(service) -> tuple[int, int]:
    print("\nInteractive traced chat")
    print("=" * 74)
    print("Type a custom follow-up, or type 'exit' to finish.")
    failures = 0
    warnings = 0
    turn_number = 1
    while True:
        try:
            prompt = input("\nYou [evaluation] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if prompt.lower() == "exit":
            break
        if not prompt:
            continue
        turn = Turn(
            prompt=prompt,
            review_focus="Inspect whether the answer matches your intended behavior.",
        )
        turn_failures, turn_warnings = _evaluate_turn(
            service, turn, turn_number
        )
        failures += turn_failures
        warnings += turn_warnings
        turn_number += 1
    return failures, warnings


def _selected_scenarios(names: list[str] | None) -> list[Scenario]:
    if not names or "all" in names:
        return list(SCENARIOS.values())
    return [SCENARIOS[name] for name in names]


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Run live scenario conversations and display AIKA response, source, "
            "tool, route, model, and follow-up behavior."
        )
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=["all", *SCENARIOS.keys()],
        help="Scenario to run; repeat for multiple scenarios (default: all).",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List scenarios without starting AIKA or connecting to services.",
    )
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Open a traced custom chat after the selected scenarios.",
    )
    parser.add_argument(
        "--pause",
        action="store_true",
        help="Pause after each scripted scenario for easier manual review.",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Show AIKA internal debug logs while the evaluator runs.",
    )
    return parser.parse_args()


def _list_scenarios() -> None:
    print("Available scenarios:\n")
    for scenario in SCENARIOS.values():
        print(f"- {scenario.key}: {scenario.title}")
        print(f"  {scenario.purpose}")
        print(f"  Turns: {len(scenario.turns)}\n")


def main() -> int:
    args = _parse_args()
    if args.list:
        _list_scenarios()
        return 0

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.WARNING,
        format="[%(levelname)s] %(message)s",
    )
    try:
        from application.service import AikaService

        service = AikaService(
            enable_jobs=False,
            enable_reminders=False,
            enable_orchestration=False,
        )
    except Exception as exc:
        print(
            "Could not start AIKA for live evaluation: "
            f"{type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(
            "Confirm the project .venv, PostgreSQL configuration, database "
            "migrations, and Ollama service are available, then try again.",
            file=sys.stderr,
        )
        return 2

    failures = 0
    warnings = 0
    scenarios = _selected_scenarios(args.scenario)
    try:
        _print_runtime(service)
        for scenario_index, scenario in enumerate(scenarios):
            if scenario_index:
                session_result = service.start_session()
                if session_result.error:
                    print(
                        f"Could not start scenario session: {session_result.error}",
                        file=sys.stderr,
                    )
                    failures += 1
                    break
            print(f"\n\nScenario: {scenario.title}")
            print("=" * 74)
            print(scenario.purpose)
            print(f"Session: {service.current_session_id}")
            for turn_number, turn in enumerate(scenario.turns, start=1):
                turn_failures, turn_warnings = _evaluate_turn(
                    service, turn, turn_number
                )
                failures += turn_failures
                warnings += turn_warnings
            if args.pause:
                try:
                    input("\nPress Enter for the next scenario...")
                except (EOFError, KeyboardInterrupt):
                    break

        if args.interactive:
            interactive_failures, interactive_warnings = _run_interactive(service)
            failures += interactive_failures
            warnings += interactive_warnings
    finally:
        service.close(wait=True)

    print("\n\nEvaluation summary")
    print("=" * 74)
    print(f"Mechanical failures: {failures}")
    print(f"Behavior warnings for manual review: {warnings}")
    print(
        "Warnings are observations, not automatic proof of a bug. Review the "
        "printed response and focus note for each turn."
    )
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
