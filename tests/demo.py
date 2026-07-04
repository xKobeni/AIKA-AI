#!/usr/bin/env python3
"""
AIKA AI - Interactive Feature Demo
====================================
Guided tour of AIKA's features with mocked responses.
No external dependencies required (Ollama, PostgreSQL not needed).

Usage:
    python tests/demo.py
    python tests/demo.py --section 3      # Jump to section 3
    python tests/demo.py --list           # List all sections
"""
import sys
import os
import time
import tempfile
import argparse
from unittest.mock import MagicMock, patch
from pathlib import Path

SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
sys.path.insert(0, SRC_DIR)

try:
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.markdown import Markdown
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("Warning: 'rich' not installed. Using plain text output.")
    print("Install with: pip install rich")


SEPARATOR = "=" * 60


def section_header(num, title):
    if HAS_RICH:
        console = Console()
        console.print()
        console.print(Panel(
            f"[bold white]Section {num}:[/bold white] {title}",
            border_style="bright_blue",
            box=box.DOUBLE,
        ))
    else:
        print(f"\n{SEPARATOR}")
        print(f"  Section {num}: {title}")
        print(SEPARATOR)


def demo_step(description, code=None, result=None):
    if HAS_RICH:
        console = Console()
        console.print(f"\n  [bold cyan]>[/bold cyan] {description}")
        if code:
            console.print(Panel(code, border_style="dim", title="Code"))
        if result:
            console.print(Panel(result, border_style="green", title="Result"))
    else:
        print(f"\n  > {description}")
        if code:
            print(f"    Code: {code}")
        if result:
            print(f"    Result: {result}")


def demo_1_settings():
    section_header(1, "Settings & Configuration")
    from config.settings import Settings

    s = Settings()
    demo_step("Load AIKA settings",
        code="from config.settings import Settings\ns = Settings()",
        result=f"chat_model={s.chat_model}, fast={s.fast_model}, smart={s.smart_model}")

    demo_step("Streaming & native tool calling enabled by default",
        result=f"streaming={s.streaming_enabled}, native_tools={s.native_tool_calling}")

    demo_step("Safety settings active",
        result=f"confirm_high={s.tool_call_confirm_high_permission}, audit={s.audit_log_enabled}")

    demo_step("Protected paths (glob patterns)",
        result=f"paths={s.protected_paths}")


def demo_2_memory():
    section_header(2, "Memory System")
    from brain.common import FAIL_PHRASES, DANGER_PHRASES
    from memory.memory_retrieval_service import MemoryRetrievalService

    demo_step("Memory system: store, retrieve, search",
        code='MemoryRetrievalService\n  .retrieve(agent_id=None, query=...)\n  .search(agent_id=None, query=..., category=...)',
        result="All memory operations accept agent_id for isolation")

    demo_step("Safety: fail phrases & danger phrases",
        result=f"fail phrases: {len(FAIL_PHRASES)}, danger phrases: {len(DANGER_PHRASES)}")


def demo_3_tools():
    section_header(3, "Tool System")
    from tools.calculator_tool import CalculatorTool
    from tools.base_tool import BaseTool

    calc = CalculatorTool()
    result = calc.execute(expression="2 + 3 * 4")
    demo_step("Calculator: safe AST-based math evaluation",
        code='calc.execute(expression="2 + 3 * 4")',
        result=f'result={result["result"]}')

    schema = calc.get_native_schema()
    demo_step("Native schema for Ollama tool calling (OpenAI format)",
        code='calc.get_native_schema()',
        result=f'type={schema["type"]}, function={schema["function"]["name"]}')

    demo_step("All tools inherit from BaseTool with native schema support",
        code='class BaseTool:\n    def get_native_schema(self) -> dict: ...')


def demo_4_tool_scoping():
    section_header(4, "Agent Tool Scoping")
    from agents.agent_profile import AgentProfile

    aika = AgentProfile(id="aika", name="Aika", role="coordinator")
    demo_step("Default agent has access to ALL tools",
        result=f"aika.allowed_tools={aika.allowed_tools} (None = all)")

    researcher = AgentProfile(id="researcher", name="Researcher",
                              role="research", allowed_tools=["web_search", "memory_store"])
    demo_step("Researcher agent: scoped to web_search + memory_store",
        code='AgentProfile(allowed_tools=["web_search", "memory_store"])',
        result=f"researcher.allowed_tools={researcher.allowed_tools}")

    demo_step("3-layer defense: prompt filtering -> parser rejection -> execution blocking",
        result="Disallowed tools are silently blocked at all layers")


def demo_5_agents():
    section_header(5, "Multi-Agent System")
    from agents.agent_registry import AgentRegistry
    import tempfile

    with tempfile.TemporaryDirectory() as tmpdir:
        registry = AgentRegistry(data_path=os.path.join(tmpdir, "agents.json"))

        table = Table(title="Configured Agents", box=box.ROUNDED)
        table.add_column("ID", style="cyan")
        table.add_column("Name", style="white")
        table.add_column("Role", style="green")
        table.add_column("Model", style="yellow")

        for aid in ["aika", "researcher", "planner", "writer"]:
            agent = registry.get(aid)
            if agent:
                table.add_row(agent.id, agent.name, agent.role or "general", agent.model or "default")

        if HAS_RICH:
            Console().print(table)
        else:
            print("  aika       | Aika       | coordinator | default")
            print("  researcher | Researcher | research    | default")
            print("  planner    | Planner    | planning    | default")
            print("  writer     | Writer     | writing     | default")

        demo_step("Agents are persisted as JSON",
            code=f'AgentRegistry(data_path="{tmpdir}/agents.json")')

        demo_step("CLI commands: 'list agents', 'use <id>', 'create agent <id> <name>'")


def demo_6_orchestration():
    section_header(6, "Orchestration Modes")
    from brain.orchestrator import Orchestrator

    demo_step("Chain mode: sequential agent pipeline",
        code='orchestrator.chain(\n    agents=["researcher", "planner", "writer"],\n    task="Research and write about AI"\n)',
        result="Each agent receives output from the previous")

    demo_step("Parallel mode: concurrent execution",
        code='orchestrator.parallel(\n    agents=["researcher", "planner"],\n    task="Gather info"\n)',
        result="Thread pool (4 workers) executes simultaneously")

    demo_step("Delegate mode: hand off to specialist",
        code='brain.route("Research quantum computing")\n# -> detects intent -> delegates to researcher',
        result="Automatic intent detection routes to best agent")

    demo_step("Team mode: multi-turn conversation",
        code='orchestrator.team(\n    agents=["aika", "researcher", "planner"],\n    task="Plan a project"\n)',
        result="Agents collaborate until [TEAM_DONE] or max turns (10)")


def demo_7_streaming():
    section_header(7, "Streaming Responses")
    from llm.ollama_client import OllamaClient

    demo_step("Streaming enabled by default",
        code='settings.streaming_enabled  # True',
        result="Token-by-token output via generate_stream() / chat_stream()")

    demo_step("AgentLoop streams final response",
        code='agent_loop.run_stream(query="Hello")\n# -> tool iterations buffer silently\n# -> final free-text response streams to user',
        result="User sees tokens appear in real-time")

    demo_step("CLI streams output token-by-token",
        code='python main.py  # Now streams instead of buffering',
        result="Responsive UX for long responses")


def demo_8_native_tools():
    section_header(8, "Native Ollama Tool Calling")
    from tools.tool_manager import ToolManager

    tm = ToolManager()
    schemas = tm.get_native_tool_schemas()

    demo_step("All tools expose OpenAI-format schemas",
        code='tm.get_native_tool_schemas()\n# Returns list of {type: "function", function: {...}}',
        result=f"{len(schemas)} tools registered for native calling")

    demo_step("AgentLoop passes tools= to Ollama API",
        code='response = ollama.chat(model=..., messages=..., tools=schemas)',
        result="Ollama natively parses tool calls (no JSON text-parsing)")

    demo_step("Automatic fallback for models without native support",
        code='if native_tool_calling and has_tools:\n    # Use Ollama native tools\nelse:\n    # Fallback: JSON text-parsing via LLMToolRouter',
        result="Works with any model")


def demo_9_safety():
    section_header(9, "Safety Guardrails")
    from brain.common import DANGER_PHRASES
    import fnmatch

    demo_step("HIGH permission tools require confirmation",
        code='tool_manager.execute_tool("shell", {"command": "rm -rf /"})',
        result="User prompted: 'Allow? [y/N]'")

    demo_step("Danger phrase detection",
        code='DANGER_PHRASES = ["delete", "remove", "destroy", "drop", ...]',
        result=f"{len(DANGER_PHRASES)} dangerous action keywords tracked")

    demo_step("Protected path patterns (glob matching)",
        code='fnmatch.fnmatch("secret.key", "*.key")  # True\nfnmatch.fnmatch(".git/config", ".git/*")  # True',
        result="File ops blocked for .env, .git, *.key, *.pem, etc.")

    demo_step("Audit logging (JSONL format)",
        code='tool_manager._audit_log("shell", {"command": "echo hi"}, True)',
        result="All tool calls logged to logs/audit.log")


def demo_10_planner():
    section_header(10, "Planner & Research Pipeline")
    demo_step("Planner: intent detection + task decomposition",
        code='planner.create_plan("Research quantum computing applications")\n# Returns structured plan with research tasks',
        result="Plan: research -> analyze -> summarize")

    demo_step("Research pipeline: search -> extract -> rank -> summarize",
        code='Pipeline: query -> web_search -> extract_content -> rank_sources -> generate_report',
        result="Automated research from query to report")

    demo_step("Content processor: cleans HTML, extracts text",
        result="Removes boilerplate, normalizes whitespace")

    demo_step("Source ranker: scores URLs by relevance",
        result="Academic > news > blogs > forums")


def demo_11_test_suite():
    section_header(11, "Comprehensive Test Suite")
    demo_step("100 tests across 14 categories",
        code='python tests/test_all.py              # Run all (mocked, ~1.5s)\npython tests/test_all.py --verbose      # Show input/output\npython tests/test_all.py --category safety  # One category\npython tests/test_all.py --list              # List categories',
        result="100% pass rate, no external dependencies")

    demo_step("Categories: Settings, Memory, Calculator, File Ops, Web, System, Memory Tools, Agent, Brain, Agent Loop, Orchestration, Safety, Streaming, Planner")


SECTIONS = [
    ("Settings & Configuration", demo_1_settings),
    ("Memory System", demo_2_memory),
    ("Tool System", demo_3_tools),
    ("Agent Tool Scoping", demo_4_tool_scoping),
    ("Multi-Agent System", demo_5_agents),
    ("Orchestration Modes", demo_6_orchestration),
    ("Streaming Responses", demo_7_streaming),
    ("Native Ollama Tool Calling", demo_8_native_tools),
    ("Safety Guardrails", demo_9_safety),
    ("Planner & Research Pipeline", demo_10_planner),
    ("Comprehensive Test Suite", demo_11_test_suite),
]


def main():
    parser = argparse.ArgumentParser(description="AIKA Feature Demo")
    parser.add_argument("--section", type=int, help="Run a specific section (1-11)")
    parser.add_argument("--list", action="store_true", help="List all sections")
    args = parser.parse_args()

    if HAS_RICH:
        console = Console()
        console.print()
        console.print(Panel(
            "[bold bright_blue]AIKA AI - Feature Demo[/bold bright_blue]\n"
            "[dim]Guided tour of AIKA's capabilities (all mocked, no dependencies)[/dim]",
            border_style="bright_blue",
            box=box.DOUBLE,
        ))
    else:
        print(f"\n{SEPARATOR}")
        print("  AIKA AI - Feature Demo")
        print(f"{SEPARATOR}\n")

    if args.list:
        print("Available sections:")
        for i, (name, _) in enumerate(SECTIONS, 1):
            print(f"  {i:2d}. {name}")
        return

    if args.section:
        if 1 <= args.section <= len(SECTIONS):
            name, fn = SECTIONS[args.section - 1]
            fn()
        else:
            print(f"Invalid section: {args.section}. Use 1-{len(SECTIONS)}.")
        return

    for i, (name, fn) in enumerate(SECTIONS, 1):
        try:
            fn()
        except Exception as e:
            if HAS_RICH:
                Console().print(f"[red]Error in section {i}: {e}[/red]")
            else:
                print(f"Error in section {i}: {e}")

    if HAS_RICH:
        console.print()
        console.print(Panel(
            "[bold green]Demo Complete![/bold green]\n"
            "[dim]Run 'python main.py' to start chatting with AIKA.[/dim]",
            border_style="green",
            box=box.DOUBLE,
        ))
    else:
        print(f"\n{SEPARATOR}")
        print("  Demo Complete!")
        print(f"{SEPARATOR}\n")


if __name__ == "__main__":
    main()
