#!/usr/bin/env python3
"""
AIKA Comprehensive Test Suite
===
Tests all AIKA features with Rich-formatted output.

Usage:
    python tests/test_all.py                # Mocked mode (fast, ~30s)
    python tests/test_all.py --live         # Live mode (needs Ollama + PostgreSQL)
    python tests/test_all.py --verbose      # Show input/output details
    python tests/test_all.py --category safety   # Run one category
    python tests/test_all.py --list              # List all categories
"""

import sys
import os
import time
import json
import inspect
import argparse
import tempfile
import shutil
import fnmatch
from pathlib import Path
from dataclasses import dataclass, field
from typing import Callable, Optional, Any
from unittest import SkipTest
from unittest.mock import patch, MagicMock, PropertyMock
from io import StringIO

# --- Path setup ---
SRC_DIR = str(Path(__file__).resolve().parent.parent / "src")
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)

# --- Rich imports ---
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
    from rich.text import Text
    from rich.columns import Columns
    from rich import box
    from rich.rule import Rule
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("ERROR: 'rich' library not installed. Run: pip install rich")
    sys.exit(1)


# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-
# TEST FRAMEWORK
# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-

@dataclass
class TestResult:
    name: str
    category: str
    passed: bool
    duration: float
    error: Optional[str] = None
    skipped: bool = False
    input_desc: str = ""
    output_desc: str = ""

@dataclass
class CategoryResults:
    name: str
    results: list = field(default_factory=list)

    @property
    def passed(self): return sum(1 for r in self.results if r.passed and not r.skipped)
    @property
    def failed(self): return sum(1 for r in self.results if not r.passed and not r.skipped)
    @property
    def skipped(self): return sum(1 for r in self.results if r.skipped)
    @property
    def total(self): return len(self.results)
    @property
    def duration(self): return sum(r.duration for r in self.results)


class AikaTestRunner:
    def __init__(self, live_mode=False, verbose=False):
        import io
        self._stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
        self.console = Console(file=self._stdout, force_terminal=True)
        self.live_mode = live_mode
        self.verbose = verbose
        self.categories: dict[str, CategoryResults] = {}
        self.all_results: list[TestResult] = []
        self.current_category: Optional[str] = None
        self._pass_count = 0
        self._fail_count = 0
        self._skip_count = 0

    def register_category(self, name: str):
        self.categories[name] = CategoryResults(name=name)

    def run_test(self, category: str, name: str, test_fn: Callable):
        start = time.time()
        try:
            sig = inspect.signature(test_fn)
            if 'runner' in sig.parameters:
                ret = test_fn(runner=self)
            else:
                ret = test_fn()
            elapsed = time.time() - start
            result = TestResult(name, category, True, elapsed)
            if self.verbose and isinstance(ret, tuple) and len(ret) == 2:
                result.input_desc, result.output_desc = ret
            self._pass_count += 1
        except AssertionError as e:
            elapsed = time.time() - start
            result = TestResult(name, category, False, elapsed, str(e)[:200])
            self._fail_count += 1
        except SkipTest as e:
            elapsed = time.time() - start
            result = TestResult(
                name, category, True, elapsed,
                str(e) or "skipped", skipped=True
            )
            self._skip_count += 1
        except Exception as e:
            elapsed = time.time() - start
            result = TestResult(name, category, False, elapsed, f"{type(e).__name__}: {str(e)[:150]}")
            self._fail_count += 1

        self.all_results.append(result)
        self.categories[category].results.append(result)
        return result

    def skip_test(self, category: str, name: str, reason: str):
        result = TestResult(name, category, True, 0.0, skipped=True)
        result.error = reason
        self._skip_count += 1
        self.all_results.append(result)
        self.categories[category].results.append(result)
        return result

    def display_header(self):
        self.console.print()
        mode_text = 'LIVE (real Ollama + PostgreSQL)' if self.live_mode else 'MOCKED (fast, no dependencies)'
        self.console.print(Panel.fit(
            "[bold cyan]AIKA AI[/] --- Comprehensive Test Suite\n"
            f"[dim]Mode: {mode_text}[/]",
            border_style="cyan",
            box=box.DOUBLE
        ))
        self.console.print()

    def display_category_start(self, name: str, test_count: int):
        self.console.print(Rule(f"[bold yellow]{name}[/] [dim]({test_count} tests)[/]", style="yellow"))
        self.console.print()

    def display_test_result(self, result: TestResult):
        if result.skipped:
            icon = "[yellow]~[/]"
            status = "[yellow]SKIP[/]"
        elif result.passed:
            icon = "[green]+[/]"
            status = "[green]PASS[/]"
        else:
            icon = "[red]X[/]"
            status = "[red]FAIL[/]"

        time_str = f"[dim]{result.duration*1000:.1f}ms[/]"
        line = f"  {icon} {status}  {result.name}  {time_str}"
        self.console.print(line)
        if result.error and not result.passed:
            self.console.print(f"       [red]  -> {result.error}[/]")
        if self.verbose and (result.input_desc or result.output_desc):
            if result.input_desc:
                self.console.print(f"       [cyan]Input:  {result.input_desc}[/]")
            if result.output_desc:
                self.console.print(f"       [green]Output: {result.output_desc}[/]")

    def display_summary(self):
        self.console.print()
        self.console.print(Rule("[bold]SUMMARY", style="bold"))
        self.console.print()

        table = Table(box=box.SIMPLE_HEAVY, show_lines=False)
        table.add_column("Category", style="bold")
        table.add_column("Tests", justify="right")
        table.add_column("Passed", justify="right", style="green")
        table.add_column("Failed", justify="right", style="red")
        table.add_column("Skipped", justify="right", style="yellow")
        table.add_column("Time", justify="right", style="dim")

        for name, cat in self.categories.items():
            table.add_row(
                name,
                str(cat.total),
                str(cat.passed),
                str(cat.failed),
                str(cat.skipped),
                f"{cat.duration:.2f}s"
            )

        table.add_section()
        total_tests = len(self.all_results)
        total_passed = sum(1 for r in self.all_results if r.passed and not r.skipped)
        total_failed = sum(1 for r in self.all_results if not r.passed and not r.skipped)
        total_skipped = sum(1 for r in self.all_results if r.skipped)
        total_time = sum(r.duration for r in self.all_results)

        table.add_row(
            "[bold]TOTAL[/]",
            f"[bold]{total_tests}[/]",
            f"[bold green]{total_passed}[/]",
            f"[bold red]{total_failed}[/]",
            f"[bold yellow]{total_skipped}[/]",
            f"[bold]{total_time:.2f}s[/]"
        )

        self.console.print(table)
        self.console.print()

        pass_rate = (total_passed / max(total_tests - total_skipped, 1)) * 100
        if total_failed == 0:
            self.console.print(Panel.fit(
                f"[bold green]ALL TESTS PASSED[/] ({total_passed}/{total_tests - total_skipped})\n"
                f"Pass rate: [bold]{pass_rate:.1f}%[/] | Time: {total_time:.2f}s",
                border_style="green", box=box.DOUBLE
            ))
        else:
            self.console.print(Panel.fit(
                f"[bold red]{total_failed} TESTS FAILED[/] ({total_passed}/{total_tests - total_skipped} passed)\n"
                f"Pass rate: [bold]{pass_rate:.1f}%[/] | Time: {total_time:.2f}s",
                border_style="red", box=box.DOUBLE
            ))
        self.console.print()

    def list_categories(self):
        self.console.print(Panel.fit("[bold]Available Test Categories", border_style="cyan"))
        for i, name in enumerate(self.categories.keys(), 1):
            self.console.print(f"  [cyan]{i}.[/] {name}")
        self.console.print(f"\n[dim]Run: python tests/test_all.py --category <name>[/]")

    def run_all(self, category_filter=None):
        self.display_header()

        categories_to_run = list(self.categories.keys())
        if category_filter:
            if category_filter not in self.categories:
                self.console.print(f"[red]Category '{category_filter}' not found.[/]")
                self.list_categories()
                return
            categories_to_run = [category_filter]

        total_tests = sum(len(self.categories[c].results) for c in categories_to_run)

        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=self.console
        ) as progress:
            task = progress.add_task("Testing...", total=total_tests)

            for cat_name in categories_to_run:
                cat = self.categories[cat_name]
                self.display_category_start(cat_name, len(cat.results))

                for result in cat.results:
                    self.display_test_result(result)
                    progress.update(task, advance=1)

                self.console.print()

        self.display_summary()


# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-
# MOCK SETUP (non-live mode)
# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-

def setup_mocks():
    """Set up all mocks for non-live mode."""
    mock_settings = MagicMock()
    # LLM
    mock_settings.chat_model = "qwen2.5:3b"
    mock_settings.fast_model = "qwen2.5:3b"
    mock_settings.smart_model = "llama3:8b"
    mock_settings.embedding_model = "nomic-embed-text"
    mock_settings.ollama_host = "http://localhost:11434"
    mock_settings.llm_timeout = 30
    # Memory
    mock_settings.memory_retrieval_limit = 8
    mock_settings.memory_candidate_multiplier = 3
    mock_settings.memory_min_score = 0.3
    mock_settings.memory_recency_half_life_hours = 720
    mock_settings.memory_sim_weight = 0.50
    mock_settings.memory_importance_weight = 0.20
    mock_settings.memory_profile_weight = 0.10
    mock_settings.memory_access_weight = 0.05
    mock_settings.memory_recency_weight = 0.15
    mock_settings.memory_category_boost_project = 0.3
    mock_settings.memory_category_boost_goal = 0.2
    mock_settings.memory_category_boost_skill = 0.1
    mock_settings.memory_max_per_category = 2
    mock_settings.memory_validator_min_score = 0.92
    mock_settings.memory_dedup_threshold = 0.92
    mock_settings.memory_extraction_max_per_message = 3
    # Context
    mock_settings.max_context_tokens = 3000
    mock_settings.max_profile_per_category = 2
    mock_settings.recent_conversations_count = 10
    mock_settings.context_session_summaries_count = 5
    mock_settings.context_cross_session_conversations = 5
    # Conversation
    mock_settings.conversation_max_count = 100
    # Tools
    mock_settings.web_search_max_results = 5
    mock_settings.tool_calling_enabled = True
    mock_settings.tool_call_max_params_length = 5000
    # Planner
    mock_settings.plan_web_search_max_results = 5
    mock_settings.plan_top_sources_count = 3
    mock_settings.crawl_content_max_chars = 2000
    # Agent
    mock_settings.agent_max_iterations = 5
    mock_settings.agent_reflection_enabled = True
    # Input
    mock_settings.max_input_length = 10000
    mock_settings.max_calculation_length = 200
    # File tools
    mock_settings.file_search_root_path = "."
    mock_settings.file_read_encoding = "utf-8"
    mock_settings.file_write_enabled = True
    mock_settings.file_write_encoding = "utf-8"
    mock_settings.file_delete_enabled = True
    mock_settings.file_grep_max_results = 50
    # Paths
    mock_settings.execution_log_path = "logs/execution.log"
    mock_settings.memory_data_path = "data/memories"
    mock_settings.conversation_data_path = "data/conversations"
    # OS / Shell
    mock_settings.shell_enabled = True
    mock_settings.shell_timeout = 30
    mock_settings.shell_blocked_keywords = [
        "rm -rf", "format", "del /", "shutdown", "rd /s",
        "del /f", "format c:", "diskpart"
    ]
    mock_settings.app_launcher_enabled = True
    mock_settings.app_launcher_uwp_enabled = True
    # Streaming
    mock_settings.streaming_enabled = True
    # Native tool calling
    mock_settings.native_tool_calling = True
    # Safety
    mock_settings.tool_call_confirm_high_permission = True
    mock_settings.audit_log_enabled = True
    mock_settings.audit_log_path = "logs/audit.log"
    mock_settings.protected_paths = [".env", ".git", ".gitignore", "*.key", "*.pem", "*.env"]
    # Persona
    mock_settings.persona_path = "src/config/persona.txt"
    # Logging
    mock_settings.log_level = "DEBUG"
    mock_settings.log_format = "[%(levelname)s] %(message)s"

    def _load_persona():
        return "You are AIKA, a helpful AI companion."
    mock_settings.load_persona = _load_persona
    mock_settings.reload = MagicMock()

    return mock_settings


# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-
# TEST FUNCTIONS --- organized by category
# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-

def make_assert(condition, msg="Assertion failed"):
    if not condition:
        raise AssertionError(msg)


# --- 1. SETTINGS & CONFIG ---

def test_settings_default_chat_model():
    from config.settings import Settings
    with patch.dict("os.environ", {}, clear=False):
        s = Settings()
        assert s.chat_model in ("qwen2.5:3b", "llama3:8b"), f"Unexpected chat_model: {s.chat_model}"
    return "Settings().chat_model", repr(s.chat_model)

def test_settings_default_fast_model():
    from config.settings import Settings
    s = Settings()
    assert s.fast_model == "qwen2.5:3b"
    return "Settings().fast_model", repr(s.fast_model)

def test_settings_default_smart_model():
    from config.settings import Settings
    s = Settings()
    assert s.smart_model == "llama3:8b"
    return "Settings().smart_model", repr(s.smart_model)

def test_settings_default_streaming():
    from config.settings import Settings
    s = Settings()
    assert s.streaming_enabled is True
    return "Settings().streaming_enabled", repr(s.streaming_enabled)

def test_settings_default_native_tool_calling():
    from config.settings import Settings
    s = Settings()
    assert s.native_tool_calling is True
    return "Settings().native_tool_calling", repr(s.native_tool_calling)

def test_settings_default_safety():
    from config.settings import Settings
    s = Settings()
    assert s.tool_call_confirm_high_permission is True
    assert s.audit_log_enabled is True
    return "confirm_high=True, audit=True", "Both enabled"

def test_settings_protected_paths():
    from config.settings import Settings
    s = Settings()
    assert ".env" in s.protected_paths
    assert "*.key" in s.protected_paths
    assert "*.pem" in s.protected_paths
    return "Settings().protected_paths", repr(s.protected_paths)

def test_settings_all_attributes_exist():
    from config.settings import DEFAULT_LOG_FORMAT, Settings
    s = Settings()
    required = [
        "database_url", "chat_model", "fast_model", "smart_model",
        "embedding_model", "ollama_host", "llm_timeout",
        "memory_retrieval_limit", "memory_sim_weight",
        "tool_calling_enabled", "streaming_enabled", "native_tool_calling",
        "tool_call_confirm_high_permission", "audit_log_enabled",
        "protected_paths", "shell_enabled", "shell_timeout",
        "persona_path", "log_level",
    ]
    for attr in required:
        assert hasattr(s, attr), f"Missing attribute: {attr}"
    with patch.dict("os.environ", {"LOG_FORMAT": "json"}):
        invalid_format_settings = Settings()
    assert invalid_format_settings.log_format == DEFAULT_LOG_FORMAT
    return "Settings() has all attributes", "All present"


# --- 2. MEMORY SYSTEM ---

def test_fail_phrases_exist():
    from brain.common import FAIL_PHRASES
    assert len(FAIL_PHRASES) >= 5
    assert "error" in FAIL_PHRASES
    assert "not found" in FAIL_PHRASES
    return "FAIL_PHRASES", f"{len(FAIL_PHRASES)} phrases"

def test_danger_phrases_exist():
    from brain.common import DANGER_PHRASES
    assert len(DANGER_PHRASES) >= 5
    assert "deleted" in DANGER_PHRASES
    assert "removed" in DANGER_PHRASES
    return "DANGER_PHRASES", f"{len(DANGER_PHRASES)} phrases"

def test_memory_extraction_patterns():
    from handlers.memory_extractor import MEMORY_PATTERNS
    assert len(MEMORY_PATTERNS) >= 5, f"Expected >= 5 categories, got {len(MEMORY_PATTERNS)}"
    for category, triggers in MEMORY_PATTERNS:
        assert len(triggers) > 0, f"Empty triggers for {category}"
        for trigger in triggers:
            assert len(trigger) > 0, f"Empty trigger in {category}"
    return f"{len(MEMORY_PATTERNS)} categories", "All triggers valid"

def test_memory_ranker_weights_sum():
    from config.settings import Settings
    s = Settings()
    weights = [
        s.memory_sim_weight,
        s.memory_importance_weight,
        s.memory_profile_weight,
        s.memory_access_weight,
        s.memory_recency_weight,
    ]
    total = sum(weights)
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"
    return "5 ranker weights", f"Sum = {total}"

def test_memory_category_boosts():
    from handlers.memory_extractor import CATEGORY_WEIGHTS
    assert len(CATEGORY_WEIGHTS) >= 5, f"Expected >= 5 categories, got {len(CATEGORY_WEIGHTS)}"
    for cat, weight in CATEGORY_WEIGHTS.items():
        assert isinstance(weight, (int, float)), f"Non-numeric weight for {cat}"
        assert weight >= 0, f"Negative weight for {cat}: {weight}"
    return f"{len(CATEGORY_WEIGHTS)} categories", "All weights valid"

def test_memory_dedup_threshold():
    from config.settings import Settings
    s = Settings()
    assert 0 < s.memory_dedup_threshold <= 1.0
    return "dedup_threshold", repr(s.memory_dedup_threshold)

def test_memory_max_per_category():
    from config.settings import Settings
    s = Settings()
    assert s.memory_max_per_category >= 1
    return "max_per_category", repr(s.memory_max_per_category)

def test_memory_scoring_cosine_identical():
    from repositories.memory_repository import MemoryRepository
    import math
    repo = MemoryRepository()
    sim = repo.cosine_similarity([1.0, 0.0, 0.0], [1.0, 0.0, 0.0])
    assert abs(sim - 1.0) < 0.001, f"Expected ~1.0, got {sim}"
    return "[1,0,0] vs [1,0,0]", f"cosine = {sim}"

def test_memory_scoring_cosine_opposite():
    from repositories.memory_repository import MemoryRepository
    repo = MemoryRepository()
    sim = repo.cosine_similarity([1.0, 0.0], [-1.0, 0.0])
    assert abs(sim - (-1.0)) < 0.001, f"Expected ~-1.0, got {sim}"
    return "[1,0] vs [-1,0]", f"cosine = {sim}"


# --- 3. TOOLS --- MATH ---

def test_calculator_basic_add():
    from tools.calculator_tool import CalculatorTool
    calc = CalculatorTool()
    result = calc.execute(expression="2 + 3")
    assert result["success"] is True
    assert result["result"] == "5"

    return 'expression="2 + 3"', 'result["result"]'
def test_calculator_basic_multiply():
    from tools.calculator_tool import CalculatorTool
    calc = CalculatorTool()
    result = calc.execute(expression="4 * 5")
    assert result["success"] is True
    assert result["result"] == "20"

    return 'expression="4 * 5"', 'result["result"]'
def test_calculator_divide_by_zero():
    from tools.calculator_tool import CalculatorTool
    calc = CalculatorTool()
    result = calc.execute(expression="1 / 0")
    assert result["success"] is False
    assert "error" in result

    return 'expression="1 / 0"', 'result["error"]'
def test_calculator_all_operators():
    from tools.calculator_tool import CalculatorTool
    calc = CalculatorTool()
    tests = [
        ("10 + 5", "15"),
        ("10 - 5", "5"),
        ("10 * 5", "50"),
        ("10 / 4", "2.5"),
        ("10 // 3", "3"),
        ("2 ** 10", "1024"),
        ("10 % 3", "1"),
    ]
    for expr, expected in tests:
        result = calc.execute(expression=expr)
        assert result["success"] is True, f"Failed for {expr}: {result}"
        assert result["result"] == expected, f"{expr}: expected {expected}, got {result['result']}"

    return "7 operators", "10+5=15, 10-5=5, 10*5=50"
def test_calculator_negative():
    from tools.calculator_tool import CalculatorTool
    calc = CalculatorTool()
    result = calc.execute(expression="-5 + 3")
    assert result["success"] is True
    assert result["result"] == "-2"


    return 'expression="-5 + 3"', 'result["result"]'
# --- 4. TOOLS --- FILE OPERATIONS ---

def test_file_write_and_read():
    from tools.file_write_tool import FileWriteTool
    from tools.file_read_tool import FileReadTool
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool()
        read_tool = FileReadTool()
        test_file = os.path.join(tmpdir, "test.txt")
        result = write_tool.execute(file_path=test_file, content="hello world", root_path=tmpdir)
        assert result["success"] is True
        result = read_tool.execute(file_path=test_file, root_path=tmpdir)
        assert result["success"] is True
        assert "hello world" in str(result)

    return 'write "hello world"', 'result'
def test_file_write_protected_path():
    from tools.file_write_tool import FileWriteTool
    tool = FileWriteTool()
    result = tool.execute(file_path=".env", content="SECRET=123")
    assert result["success"] is False
    assert "protected" in result["error"].lower()

    return 'write ".env', 'protected'
def test_file_delete_protected_path():
    from tools.file_delete_tool import FileDeleteTool
    tool = FileDeleteTool()
    result = tool.execute(file_path=".env")
    assert result["success"] is False
    assert "protected" in result["error"].lower()

    return 'delete ".env', 'protected'
def test_file_write_traversal_blocked():
    from tools.file_write_tool import FileWriteTool
    tool = FileWriteTool()
    result = tool.execute(file_path="../../etc/passwd", content="test")
    assert result["success"] is False

    return 'write "../../etc/passwd', 'blocked'
def test_file_delete_traversal_blocked():
    from tools.file_delete_tool import FileDeleteTool
    tool = FileDeleteTool()
    result = tool.execute(file_path="../../etc/passwd")
    assert result["success"] is False

    return 'delete "../../etc/passwd', 'blocked'
def test_file_edit_replace():
    from tools.file_edit_tool import FileEditTool
    from tools.file_write_tool import FileWriteTool
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool()
        edit_tool = FileEditTool()
        test_file = os.path.join(tmpdir, "edit_test.txt")
        write_tool.execute(file_path=test_file, content="hello world", root_path=tmpdir)
        result = edit_tool.execute(
            file_path=test_file,
            old_text="world",
            new_text="there",
            root_path=tmpdir
        )
        assert result["success"] is True
        with open(test_file, "r") as f:
            assert "hello there" in f.read()

    return 'edit "world" -> "there', 'success'
def test_file_grep():
    from tools.file_grep_tool import FileGrepTool
    from tools.file_write_tool import FileWriteTool
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool()
        grep_tool = FileGrepTool()
        write_tool.execute(file_path="grep_test.txt", content="line1\nfoo bar\nline3\nfoo baz", root_path=tmpdir)
        result = grep_tool.execute(query="foo", path="grep_test.txt", root_path=tmpdir)
        assert result["success"] is True

    return 'grep "foo', 'matches found'
def test_file_mkdir():
    from tools.file_mkdir_tool import FileMkdirTool
    with tempfile.TemporaryDirectory() as tmpdir:
        tool = FileMkdirTool()
        result = tool.execute(dir_path="newdir", root_path=tmpdir)
        assert result["success"] is True
        assert os.path.isdir(os.path.join(tmpdir, "newdir"))

    return 'mkdir "newdir', 'created'
def test_file_append():
    from tools.file_append_tool import FileAppendTool
    from tools.file_write_tool import FileWriteTool
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool()
        append_tool = FileAppendTool()
        test_file = os.path.join(tmpdir, "append_test.txt")
        write_tool.execute(file_path=test_file, content="line1\n", root_path=tmpdir)
        result = append_tool.execute(file_path=test_file, content="line2\n", root_path=tmpdir)
        assert result["success"] is True
        with open(test_file, "r") as f:
            content = f.read()
            assert "line1" in content
            assert "line2" in content

    return 'append "line2', 'appended'
def test_file_read_range():
    from tools.file_read_range_tool import FileReadRangeTool
    from tools.file_write_tool import FileWriteTool
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool()
        range_tool = FileReadRangeTool()
        test_file = os.path.join(tmpdir, "range_test.txt")
        write_tool.execute(file_path=test_file, content="line1\nline2\nline3\nline4\nline5", root_path=tmpdir)
        result = range_tool.execute(file_path=test_file, start_line=2, end_line=4, root_path=tmpdir)
        assert result["success"] is True

    return "read lines 2-4", "content"
def test_file_delete():
    from tools.file_delete_tool import FileDeleteTool
    from tools.file_write_tool import FileWriteTool
    with tempfile.TemporaryDirectory() as tmpdir:
        write_tool = FileWriteTool()
        delete_tool = FileDeleteTool()
        test_file = os.path.join(tmpdir, "delete_test.txt")
        write_tool.execute(file_path=test_file, content="to be deleted", root_path=tmpdir)
        assert os.path.exists(test_file)
        result = delete_tool.execute(file_path=test_file, root_path=tmpdir)
        assert result["success"] is True
        assert not os.path.exists(test_file)

    return "delete test file", "deleted"
def test_file_write_content_too_large():
    from tools.file_write_tool import FileWriteTool
    tool = FileWriteTool()
    huge_content = "x" * 1_100_000
    result = tool.execute(file_path="test.txt", content=huge_content)
    assert result["success"] is False
    assert "large" in result["error"].lower() or "too" in result["error"].lower()

    return "write 1.1MB", "too large"
def test_file_write_disabled():
    from tools.file_write_tool import FileWriteTool, settings as fw_settings
    original = fw_settings.file_write_enabled
    fw_settings.file_write_enabled = False
    try:
        tool = FileWriteTool()
        result = tool.execute(file_path="test.txt", content="test")
        assert result["success"] is False
        assert "disabled" in result["error"].lower()
    finally:
        fw_settings.file_write_enabled = original

    return "write when disabled", "disabled"
def test_file_delete_disabled():
    from tools.file_delete_tool import FileDeleteTool, settings as fd_settings
    original = fd_settings.file_delete_enabled
    fd_settings.file_delete_enabled = False
    try:
        tool = FileDeleteTool()
        result = tool.execute(file_path="test.txt")
        assert result["success"] is False
        assert "disabled" in result["error"].lower()
    finally:
        fd_settings.file_delete_enabled = original

    return "delete when disabled", "disabled"
def test_file_protected_glob_key():
    from tools.file_write_tool import FileWriteTool
    tool = FileWriteTool()
    result = tool.execute(file_path="secret.key", content="key data")
    assert result["success"] is False
    assert "protected" in result["error"].lower()


    return 'write "secret.key', 'protected'
# --- 5. TOOLS --- WEB ---

def test_web_search_tool_metadata():
    from tools.web_search_tool import WebSearchTool
    tool = WebSearchTool()
    assert tool.name == "web_search"
    assert tool.description
    schema = tool.get_schema()
    assert "name" in schema
    assert "parameters" in schema

    return "tool schema", "name + description"
def test_web_search_no_results():
    from tools.web_search_tool import WebSearchTool
    mock_provider = MagicMock()
    mock_provider.search.return_value = []
    tool = WebSearchTool(provider=mock_provider)
    result = tool.execute(query="xyznonexistent12345")
    assert len(result.get("results", [])) == 0
    assert "error" in result or result.get("success") is False

    return 'query="xyznonexistent"', 'no results'
def test_web_search_provider_error():
    from tools.web_search_tool import WebSearchTool
    mock_provider = MagicMock()
    mock_provider.search.side_effect = Exception("Provider error")
    tool = WebSearchTool(provider=mock_provider)
    result = tool.execute(query="test")
    assert result["success"] is False
    assert "error" in result


    return 'query="test', 'error'
# --- 6. TOOLS --- SYSTEM ---

def test_shell_basic_command():
    from tools.shell_tool import ShellTool
    tool = ShellTool()
    with patch("tools.shell_tool.settings") as mock_s:
        mock_s.shell_enabled = True
        mock_s.shell_timeout = 30
        mock_s.shell_blocked_keywords = ["rm -rf", "format"]
        result = tool.execute(command="echo hello")
        assert result["success"] is True
        assert "hello" in result["stdout"]

    return 'command="echo hello', 'hello'
def test_shell_blocked_keyword():
    from tools.shell_tool import ShellTool
    tool = ShellTool()
    with patch("tools.shell_tool.settings") as mock_s:
        mock_s.shell_enabled = True
        mock_s.shell_timeout = 30
        mock_s.shell_blocked_keywords = ["rm -rf", "format", "del /", "shutdown"]
        result = tool.execute(command="rm -rf /")
        assert result["success"] is False
        assert "blocked" in result["error"].lower()

    return 'command="rm -rf /', 'blocked'
def test_shell_blocked_extra_patterns():
    from tools.shell_tool import ShellTool
    tool = ShellTool()
    with patch("tools.shell_tool.settings") as mock_s:
        mock_s.shell_enabled = True
        mock_s.shell_timeout = 30
        mock_s.shell_blocked_keywords = ["rm -rf", "format"]
        blocked = ["bcdedit", "diskpart", "net user", "reg add"]
        for pattern in blocked:
            result = tool.execute(command=f"some {pattern} command")
            assert result["success"] is False, f"Failed to block: {pattern}"

    return "blocked patterns", "all blocked"
def test_shell_disabled():
    from tools.shell_tool import ShellTool
    tool = ShellTool()
    with patch("tools.shell_tool.settings") as mock_s:
        mock_s.shell_enabled = False
        result = tool.execute(command="echo hello")
        assert result["success"] is False
        assert "disabled" in result["error"].lower()

    return "command when disabled", "disabled"
def test_system_info_tool():
    from tools.system_info_tool import SystemInfoTool
    tool = SystemInfoTool()
    result = tool.execute()
    assert result["success"] is True
    assert "os" in result or "os_info" in result or "OS" in str(result)

    return "system info", "OS + CPU + RAM"
def test_folder_tool_list():
    from tools.folder_tool import FolderTool
    tool = FolderTool()
    with patch("tools.folder_tool.settings") as mock_s:
        mock_s.file_search_root_path = "."
        result = tool.execute(path=".")
        assert result["success"] is True


    return "list directory", "files"
# --- 7. TOOLS --- MEMORY ---

def test_memory_search_tool_metadata():
    from tools.memory_search_tool import MemorySearchTool
    mock_service = MagicMock()
    tool = MemorySearchTool(mock_service)
    assert tool.name == "memory_search"
    schema = tool.get_schema()
    assert "name" in schema

    return "tool schema", "name"
def test_memory_search_with_results():
    from tools.memory_search_tool import MemorySearchTool
    mock_mem = MagicMock()
    mock_mem.content = "User lives in Tokyo"
    mock_service = MagicMock()
    mock_service.retrieve.return_value = [mock_mem]
    tool = MemorySearchTool(mock_service)
    result = tool.execute(query="where does user live")
    assert result["success"] is True

    return 'query="user location', 'results'
def test_memory_search_empty():
    from tools.memory_search_tool import MemorySearchTool
    mock_service = MagicMock()
    mock_service.retrieve.return_value = []
    tool = MemorySearchTool(mock_service)
    result = tool.execute(query="nonexistent topic xyz")
    assert result["success"] is True


    return 'query="nonexistent', 'no results'
# --- 8. AGENT SYSTEM ---

def test_agent_profile_create():
    from agents.agent_profile import AgentProfile
    p = AgentProfile(id="test", name="Test Agent")
    assert p.id == "test"
    assert p.name == "Test Agent"
    assert p.is_active is True
    assert p.allowed_tools is None
    assert p.max_iterations == 5

    return 'id="test"', 'profile.id'
def test_agent_profile_serialization():
    from agents.agent_profile import AgentProfile
    p = AgentProfile(id="test", name="Test Agent", model="llama3:8b", allowed_tools=["calculator"])
    d = p.to_dict()
    assert d["id"] == "test"
    assert d["model"] == "llama3:8b"
    assert d["allowed_tools"] == ["calculator"]
    p2 = AgentProfile.from_dict(d)
    assert p2.id == "test"
    assert p2.model == "llama3:8b"

    return "to_dict/from_dict", "round-trip"
def test_agent_registry_default_exists():
    from agents.agent_registry import AgentRegistry, DEFAULT_AGENT_ID
    registry = AgentRegistry()
    aika = registry.get(DEFAULT_AGENT_ID)
    assert aika is not None
    assert aika.id == "aika"
    assert aika.name == "AIKA"

    return 'registry.get("aika")', 'exists'
def test_agent_registry_create():
    from agents.agent_registry import AgentRegistry
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "agents.json")
        registry = AgentRegistry(data_path=path)
        profile = registry.create_agent("test_agent", "Test Agent")
        assert profile is not None
        assert profile.id == "test_agent"
        assert registry.get("test_agent") is not None

    return "create agent", "created"
def test_agent_registry_cannot_delete_default():
    from agents.agent_registry import AgentRegistry, DEFAULT_AGENT_ID
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "agents.json")
        registry = AgentRegistry(data_path=path)
        result = registry.delete(DEFAULT_AGENT_ID)
        assert result is False
        assert registry.get(DEFAULT_AGENT_ID) is not None

    return 'delete "aika', 'blocked'
def test_agent_registry_set_model():
    from agents.agent_registry import AgentRegistry
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "agents.json")
        registry = AgentRegistry(data_path=path)
        registry.create_agent("mymodel", "My Model Agent")
        result = registry.set_model("mymodel", "llama3:8b")
        assert result is True
        assert registry.get("mymodel").model == "llama3:8b"

    return "set model", "llama3:8b"
def test_agent_registry_set_persona():
    from agents.agent_registry import AgentRegistry
    with tempfile.TemporaryDirectory() as tmpdir:
        path = os.path.join(tmpdir, "agents.json")
        persona_path = os.path.join(tmpdir, "persona.txt")
        with open(persona_path, "w") as f:
            f.write("You are a test agent.")
        registry = AgentRegistry(data_path=path)
        registry.create_agent("mypersona", "My Persona Agent")
        result = registry.set_persona("mypersona", persona_path)
        assert result is True
        assert registry.get("mypersona").persona_path == persona_path

    return "set persona", "path"
def test_agent_tool_scoping():
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    from tools.shell_tool import ShellTool
    tm = ToolManager()
    tm.register_tool(CalculatorTool())
    tm.register_tool(ShellTool())
    result = tm.execute_tool("calculator", allowed_tool_names=["calculator"], expression="2+2")
    assert result["success"] is True

    return 'allowed_tools=["calculator"]', 'works'
def test_agent_tool_scoping_blocked():
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    from tools.shell_tool import ShellTool
    tm = ToolManager()
    tm.register_tool(CalculatorTool())
    tm.register_tool(ShellTool())
    result = tm.execute_tool("shell", allowed_tool_names=["calculator"], command="echo hi")
    assert result["success"] is False
    assert "not available" in result["error"].lower()


    return "shell not in allowed", "blocked"
# --- 9. BRAIN & ROUTING ---

def test_tool_call_parser_json():
    from brain.tool_call_parser import ToolCallParser
    parser = ToolCallParser(tool_names={"calculator", "file_read"})
    response = '{"tool": "calculator", "parameters": {"expression": "2+2"}}'
    result = parser.parse(response)
    assert result is not None
    assert result["tool"] == "calculator"
    assert result["parameters"]["expression"] == "2+2"

    return "JSON tool call", "calculator"
def test_tool_call_parser_null_tool():
    from brain.tool_call_parser import ToolCallParser
    parser = ToolCallParser(tool_names={"calculator"})
    response = '{"tool": null, "response": "Hello!"}'
    result = parser.parse(response)
    assert result is not None
    assert result["tool"] is None

    return "null tool", "response"
def test_tool_call_parser_unknown_tool():
    from brain.tool_call_parser import ToolCallParser
    parser = ToolCallParser(tool_names={"calculator"})
    response = '{"tool": "nonexistent_tool", "parameters": {}}'
    result = parser.parse(response)
    assert result is None

    return "unknown tool", "rejected"
def test_tool_call_parser_markdown_fences():
    from brain.tool_call_parser import ToolCallParser
    parser = ToolCallParser(tool_names={"calculator"})
    response = '```json\n{"tool": "calculator", "parameters": {"expression": "1+1"}}\n```'
    result = parser.parse(response)
    assert result is not None
    assert result["tool"] == "calculator"

    return "markdown JSON", "parsed"
def test_tool_call_parser_scoping():
    from brain.tool_call_parser import ToolCallParser
    parser = ToolCallParser(tool_names={"calculator"})
    response = '{"tool": "shell", "parameters": {"command": "echo hi"}}'
    result = parser.parse(response)
    assert result is None

    return "disallowed tool", "rejected"
def test_tool_result_formatter():
    from brain.tool_result_formatter import ToolResultFormatter
    formatter = ToolResultFormatter()
    result = formatter.format_for_context(
        "calculator",
        {"expression": "2+2"},
        {"success": True, "result": "4"}
    )
    assert "4" in result

    return "format result", "formatted"
def test_base_tool_native_schema():
    from tools.calculator_tool import CalculatorTool
    tool = CalculatorTool()
    schema = tool.get_native_schema()
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calculator"
    assert "parameters" in schema["function"]
    assert schema["function"]["parameters"]["type"] == "object"

    return "get_native_schema()", "OpenAI format"
def test_tool_manager_native_schemas():
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    tm = ToolManager()
    tm.register_tool(CalculatorTool())
    schemas = tm.get_native_tool_schemas()
    assert len(schemas) == 1
    assert schemas[0]["type"] == "function"


    return "get_native_tool_schemas()", "1 schema"
# --- 10. AGENT LOOP & TOOL CALLING ---

def test_agent_context_iteration_tracking():
    from brain.agent_context import AgentContext
    ctx = AgentContext("test message")
    assert ctx.iterations == 0
    ctx.iterations += 1
    assert ctx.iterations == 1

    return "iterations", "0 -> 1"
def test_agent_context_history():
    from brain.agent_context import AgentContext
    ctx = AgentContext("test message")
    ctx.add_user_message("hello")
    ctx.add_assistant_response("hi there")
    history = ctx.get_history_for_llm()
    assert len(history) >= 2

    return "get_history", "2 entries"
def test_agent_loop_max_iterations():
    from config.settings import Settings
    import brain.agent_loop as al
    s = Settings()
    assert s.agent_max_iterations >= 1, f"max_iterations too low: {s.agent_max_iterations}"
    assert hasattr(al.AgentLoop, 'run'), "AgentLoop.run missing"
    assert hasattr(al.AgentLoop, 'run_stream'), "AgentLoop.run_stream missing"
    assert callable(getattr(al.AgentLoop, 'run', None)), "AgentLoop.run not callable"
    return "AgentLoop", f"max_iterations={s.agent_max_iterations}, run+run_stream"

def test_native_tool_calling_flag():
    from config.settings import Settings
    s = Settings()
    assert hasattr(s, "native_tool_calling"), "native_tool_calling setting missing"
    assert isinstance(s.native_tool_calling, bool), f"Expected bool, got {type(s.native_tool_calling)}"
    assert s.native_tool_calling is True, f"Expected default True, got {s.native_tool_calling}"
    return "native_tool_calling", "True (default)"
def test_tool_manager_high_permission():
    from tools.tool_manager import ToolManager
    from tools.shell_tool import ShellTool
    from tools.calculator_tool import CalculatorTool
    tm = ToolManager()
    tm.register_tool(ShellTool())
    tm.register_tool(CalculatorTool())
    assert tm.is_high_permission("shell") is True
    assert tm.is_high_permission("calculator") is False

    return "is_high_permission", "shell=True, calc=False"
def test_tool_manager_validate_params_length():
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    from config.settings import settings as real_settings
    tm = ToolManager()
    tm.register_tool(CalculatorTool())
    original = real_settings.tool_call_max_params_length
    real_settings.tool_call_max_params_length = 50
    try:
        valid, error = tm.validate_tool_call("calculator", {"expression": "2+2"})
        assert valid is True, f"Expected valid, got {error}"
        valid, error = tm.validate_tool_call("calculator", {"expression": "x" * 100})
        assert valid is False, "Expected invalid for long params"
    finally:
        real_settings.tool_call_max_params_length = original

    return "validate params", "short=ok, long=fail"
def test_tool_manager_validate_unknown_tool():
    from tools.tool_manager import ToolManager
    tm = ToolManager()
    valid, error = tm.validate_tool_call("nonexistent", {})
    assert valid is False
    assert "unknown" in error.lower()


    return "unknown tool", "rejected"
# --- 11. ORCHESTRATION ---

def test_shared_context_set_get():
    from brain.shared_context import SharedContext
    ctx = SharedContext()
    ctx.set("key1", "value1", agent_id="agent_a")
    assert ctx.get("key1") == "value1"

    return "set/get", "value1"
def test_shared_context_get_all():
    from brain.shared_context import SharedContext
    ctx = SharedContext()
    ctx.set("k1", "v1", agent_id="a")
    ctx.set("k2", "v2", agent_id="b")
    all_data = ctx.get_all()
    assert len(all_data) == 2

    return "get_all", "2 items"
def test_shared_context_clear():
    from brain.shared_context import SharedContext
    ctx = SharedContext()
    ctx.set("k1", "v1", agent_id="a")
    ctx.clear()
    assert ctx.get("k1") is None

    return "clear", "empty"
def test_agent_message_task():
    from brain.agent_message import AgentMessage
    msg = AgentMessage.task(from_agent="a", to_agent="b", task_description="do something")
    assert msg.from_agent == "a"
    assert msg.to_agent == "b"
    assert msg.message_type == "task"

    return "task message", "task type"
def test_agent_message_result():
    from brain.agent_message import AgentMessage
    msg = AgentMessage.result(from_agent="b", to_agent="a", result_data="done")
    assert msg.from_agent == "b"
    assert msg.message_type == "result"

    return "result message", "result type"
def test_agent_message_serialization():
    from brain.agent_message import AgentMessage
    msg = AgentMessage.task(from_agent="a", to_agent="b", task_description="test")
    d = msg.to_dict()
    assert "from_agent" in d
    assert d["from_agent"] == "a"

    return "to_dict", "from_agent"
def test_orchestrator_delegate():
    from brain.orchestrator import Orchestrator
    from brain.shared_context import SharedContext
    mock_registry = MagicMock()
    mock_profile = MagicMock()
    mock_profile.model = None
    mock_registry.get.return_value = mock_profile
    mock_loop = MagicMock()
    mock_loop.run.return_value = "Research result here"
    orch = Orchestrator(mock_registry, mock_loop)
    result = orch.delegate("aika", "research AI", "researcher")
    assert result == "Research result here"
    mock_loop.run.assert_called_once()

    return "delegate", "Research result here"
def test_orchestrator_delegate_agent_not_found():
    from brain.orchestrator import Orchestrator
    mock_registry = MagicMock()
    mock_registry.get.return_value = None
    mock_loop = MagicMock()
    orch = Orchestrator(mock_registry, mock_loop)
    result = orch.delegate("aika", "task", "nonexistent")
    assert "not found" in result.lower()


    return "delegate missing", "not found"
# --- 12. SAFETY ---

def test_tool_manager_confirmation_accept():
    from tools.tool_manager import ToolManager
    from tools.shell_tool import ShellTool
    from config.settings import settings as real_settings
    tm = ToolManager()
    tm.register_tool(ShellTool())
    orig = real_settings.tool_call_confirm_high_permission
    real_settings.tool_call_confirm_high_permission = True
    try:
        with patch("builtins.input", return_value="y"):
            result = tm._check_confirmation("shell", {"command": "echo hi"})
            assert result is True
    finally:
        real_settings.tool_call_confirm_high_permission = orig

    return 'confirm "y"', 'True'
def test_tool_manager_confirmation_reject():
    from tools.tool_manager import ToolManager
    from tools.shell_tool import ShellTool
    from config.settings import settings as real_settings
    tm = ToolManager()
    tm.register_tool(ShellTool())
    orig = real_settings.tool_call_confirm_high_permission
    real_settings.tool_call_confirm_high_permission = True
    try:
        with patch("builtins.input", return_value="n"):
            result = tm._check_confirmation("shell", {"command": "echo hi"})
            assert result is False
    finally:
        real_settings.tool_call_confirm_high_permission = orig

    return 'confirm "n"', 'False'
def test_tool_manager_confirmation_skipped_for_low():
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    from config.settings import settings as real_settings
    tm = ToolManager()
    tm.register_tool(CalculatorTool())
    orig = real_settings.tool_call_confirm_high_permission
    real_settings.tool_call_confirm_high_permission = True
    try:
        result = tm._check_confirmation("calculator", {"expression": "2+2"})
        assert result is True
    finally:
        real_settings.tool_call_confirm_high_permission = orig

    return "calculator (low perm)", "True"
def test_tool_manager_audit_log():
    import json
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    from config.settings import settings as real_settings
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "audit.log")
        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        orig_enabled = real_settings.audit_log_enabled
        orig_path = real_settings.audit_log_path
        orig_confirm = real_settings.tool_call_confirm_high_permission
        real_settings.audit_log_enabled = True
        real_settings.audit_log_path = log_path
        real_settings.tool_call_confirm_high_permission = False
        try:
            result = tm.execute_tool("calculator", expression="2+2")
            assert result["success"] is True
            assert os.path.exists(log_path)
            with open(log_path, "r") as f:
                entries = f.readlines()
                assert len(entries) >= 1
                entry = json.loads(entries[-1])
                assert entry["tool"] == "calculator"
                assert entry["success"] is True
        finally:
            real_settings.audit_log_enabled = orig_enabled
            real_settings.audit_log_path = orig_path
            real_settings.tool_call_confirm_high_permission = orig_confirm

    return "audit enabled", "logged"
def test_tool_manager_audit_log_disabled():
    from tools.tool_manager import ToolManager
    from tools.calculator_tool import CalculatorTool
    from config.settings import settings as real_settings
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = os.path.join(tmpdir, "audit.log")
        tm = ToolManager()
        tm.register_tool(CalculatorTool())
        orig_enabled = real_settings.audit_log_enabled
        orig_path = real_settings.audit_log_path
        orig_confirm = real_settings.tool_call_confirm_high_permission
        real_settings.audit_log_enabled = False
        real_settings.audit_log_path = log_path
        real_settings.tool_call_confirm_high_permission = False
        try:
            tm.execute_tool("calculator", expression="2+2")
            assert not os.path.exists(log_path)
        finally:
            real_settings.audit_log_enabled = orig_enabled
            real_settings.audit_log_path = orig_path
            real_settings.tool_call_confirm_high_permission = orig_confirm

    return "audit disabled", "no file"
def test_file_write_protected_glob_pem():
    from tools.file_write_tool import FileWriteTool
    tool = FileWriteTool()
    result = tool.execute(file_path="server.pem", content="cert data")
    assert result["success"] is False
    assert "protected" in result["error"].lower()

    return 'write "server.pem', 'protected'
def test_file_delete_protected_git():
    from tools.file_delete_tool import FileDeleteTool
    tool = FileDeleteTool()
    result = tool.execute(file_path=".git/config")
    assert result["success"] is False
    assert "protected" in result["error"].lower()


    return 'delete ".git/config', 'protected'
# --- 13. STREAMING ---

def test_settings_streaming_default():
    from config.settings import Settings
    s = Settings()
    assert s.streaming_enabled is True

    return "streaming_enabled", "True"
def test_settings_native_tool_calling_default():
    from config.settings import Settings
    s = Settings()
    assert s.native_tool_calling is True

    return "native_tool_calling", "True"
def test_ollama_client_has_stream_methods():
    from llm.ollama_client import OllamaClient
    import inspect
    client = OllamaClient()
    assert hasattr(client, "generate_stream"), "generate_stream missing"
    assert hasattr(client, "chat_stream"), "chat_stream missing"
    assert callable(client.generate_stream), "generate_stream not callable"
    assert callable(client.chat_stream), "chat_stream not callable"
    gen_sig = inspect.signature(client.generate_stream)
    chat_sig = inspect.signature(client.chat_stream)
    assert 'prompt' in gen_sig.parameters, "generate_stream missing 'prompt' param"
    assert 'messages' in chat_sig.parameters, "chat_stream missing 'messages' param"
    return "OllamaClient", "generate_stream(prompt), chat_stream(messages)"

def test_agent_loop_has_run_stream():
    from brain.agent_loop import AgentLoop
    import inspect
    assert hasattr(AgentLoop, "run_stream"), "run_stream missing"
    assert callable(getattr(AgentLoop, "run_stream", None)), "run_stream not callable"
    sig = inspect.signature(AgentLoop.run_stream)
    assert 'user_message' in sig.parameters, "run_stream missing 'user_message' param"
    return "AgentLoop", "run_stream(user_message) -> Iterator[str]"
# --- 14. PLANNER & RESEARCH ---

def test_planner_create_plan():
    from planner.execution_planner import ExecutionPlanner
    planner = ExecutionPlanner()
    plan = planner.create_plan("research quantum computing")
    assert plan is not None
    assert len(plan.steps) >= 1

    return "research quantum computing", "plan with steps"
def test_planner_summarize_plan():
    from planner.execution_planner import ExecutionPlanner
    planner = ExecutionPlanner()
    plan = planner.create_plan("summarize machine learning")
    assert plan is not None

    return "summarize machine learning", "plan"
def test_planner_analyze_plan():
    from planner.execution_planner import ExecutionPlanner
    planner = ExecutionPlanner()
    plan = planner.create_plan("analyze the pros and cons of rust")
    assert plan is not None

    return "analyze rust vs go", "plan"
def test_planner_returns_none_for_unknown():
    from planner.execution_planner import ExecutionPlanner
    planner = ExecutionPlanner()
    plan = planner.create_plan("hello world")
    assert plan is None

    return "hello world", "None"
def test_content_processor_clean():
    from research.content_processor import ContentProcessor
    processor = ContentProcessor()
    result = processor.process([{"content": "  extra   spaces  \n\n\n newlines  "}])
    assert result is not None

    return "process pages", "cleaned"
def test_content_processor_empty():
    from research.content_processor import ContentProcessor
    processor = ContentProcessor()
    result = processor.process([])
    assert result is not None

    return "process []", "empty result"
def test_source_ranker_url_classification():
    from research.source_ranker import SourceRanker
    ranker = SourceRanker()
    sources = [
        {"url": "https://docs.python.org/3/library.html", "title": "Docs", "snippet": "Python docs"},
        {"url": "https://github.com/user/repo", "title": "GitHub", "snippet": "A repo"},
        {"url": "https://en.wikipedia.org/wiki/Python", "title": "Wikipedia", "snippet": "Python lang"},
    ]
    ranked = ranker.rank(sources)
    assert len(ranked) == 3

    return "3 URLs", "3 ranked"
def test_report_generator():
    from research.report_generator import ReportGenerator
    mock_llm = MagicMock()
    mock_llm.generate.return_value = "This is a test report about the topic."
    gen = ReportGenerator(llm=mock_llm)
    report = gen.generate(
        query="test topic",
        content="Test content for the report."
    )
    assert report is not None
    assert len(str(report)) > 0
    return "generate report", "report text"


# ===
# LIVE INTEGRATION TESTS (require --live flag + running Ollama/PostgreSQL)
# ===

def _require_live_mode(runner):
    if not runner or not runner.live_mode:
        raise SkipTest("requires --live")


def test_live_ollama_generate(runner=None):
    """Real Ollama generate call"""
    _require_live_mode(runner)
    from llm.ollama_client import OllamaClient
    client = OllamaClient()
    response = client.generate("What is 2+2? Reply with just the number.")
    assert response is not None
    assert len(response) > 0
    return "generate('What is 2+2?')", response[:80]


def test_live_ollama_chat(runner=None):
    """Real Ollama chat call with system prompt"""
    _require_live_mode(runner)
    from llm.ollama_client import OllamaClient
    client = OllamaClient()
    response = client.generate_with_model(
        "You are a calculator. User: 10 * 5. Reply with just the number.",
        model=client.model
    )
    assert response is not None
    assert "50" in response
    return "chat('10 * 5')", response[:80]


def test_live_ollama_stream(runner=None):
    """Real Ollama streaming response"""
    _require_live_mode(runner)
    from llm.ollama_client import OllamaClient
    client = OllamaClient()
    chunks = list(client.generate_stream("Say hello in one word."))
    assert len(chunks) > 0
    full = "".join(chunks)
    assert len(full) > 0
    return "stream('Say hello')", full[:80]


def test_live_calculator_then_llm(runner=None):
    """Calculator result fed to LLM for explanation"""
    _require_live_mode(runner)
    from tools.calculator_tool import CalculatorTool
    from llm.ollama_client import OllamaClient
    calc = CalculatorTool()
    result = calc.execute(expression="2**10")
    assert result["success"] is True
    client = OllamaClient()
    response = client.generate(f"The calculator returned {result['result']}. What does this number mean in computing? Reply in one sentence.")
    assert response is not None
    assert len(response) > 10
    return f"calc(2**10)={result['result']} -> LLM", response[:80]


def test_live_web_search(runner=None):
    """Real DuckDuckGo web search"""
    _require_live_mode(runner)
    from tools.web_search_tool import WebSearchTool
    tool = WebSearchTool()
    result = tool.execute(query="Python programming language", max_results=3)
    assert result["success"] is True
    assert len(result["results"]) > 0
    first = result["results"][0]
    assert "title" in first or "url" in first
    return "web_search('Python')", f"{len(result['results'])} results"


def test_live_memory_store_and_search(runner=None):
    """Real PostgreSQL memory store and search"""
    _require_live_mode(runner)
    from database.db import db_session
    from repositories.memory_repository import MemoryRepository
    from llm.embedding_service import EmbeddingService
    from handlers.memory_handler import MemoryHandler
    with db_session() as session:
        repo = MemoryRepository(session)
        embedder = EmbeddingService()
        handler = MemoryHandler(memory_repo=repo, embedding_service=embedder)
        handler.store_memory("store fact: live test integration 2026")
        results = handler.search_memories("live test")
        assert len(results) > 0
        return "store + search memory", f"{len(results)} results"


def test_live_full_agent_loop(runner=None):
    """Full agent loop with real LLM - ask a question, get tool calls, get answer"""
    _require_live_mode(runner)
    from brain.agent_loop import AgentLoop
    from tools.tool_manager import ToolManager
    from llm.ollama_client import OllamaClient
    from unittest.mock import MagicMock
    llm = OllamaClient()
    tool_manager = ToolManager()
    decision_engine = MagicMock()
    router = MagicMock()
    agent_loop = AgentLoop(
        decision_engine=decision_engine,
        router=router,
        llm=llm,
        tool_manager=tool_manager,
    )
    result = agent_loop.run("What is 5 + 3? Use the calculator tool.")
    assert result is not None
    assert len(result) > 0
    return "agent_loop('5+3')", result[:80]


def test_live_agent_loop_stream(runner=None):
    """Full agent loop with streaming response"""
    _require_live_mode(runner)
    from brain.agent_loop import AgentLoop
    from tools.tool_manager import ToolManager
    from llm.ollama_client import OllamaClient
    from unittest.mock import MagicMock
    llm = OllamaClient()
    tool_manager = ToolManager()
    decision_engine = MagicMock()
    router = MagicMock()
    agent_loop = AgentLoop(
        decision_engine=decision_engine,
        router=router,
        llm=llm,
        tool_manager=tool_manager,
    )
    chunks = list(agent_loop.run_stream("What is 10 / 2? Use the calculator."))
    assert len(chunks) > 0
    full = "".join(chunks)
    assert "5" in full
    return "stream('10/2')", full[:80]


# ===
# TEST REGISTRATION
# ===


def register_all_tests(runner: AikaTestRunner):
    """Register all test functions organized by category."""

    # 1. Settings & Config
    runner.register_category("Settings & Config")
    for fn in [
        test_settings_default_chat_model,
        test_settings_default_fast_model,
        test_settings_default_smart_model,
        test_settings_default_streaming,
        test_settings_default_native_tool_calling,
        test_settings_default_safety,
        test_settings_protected_paths,
        test_settings_all_attributes_exist,
    ]:
        runner.run_test("Settings & Config", fn.__doc__ or fn.__name__, fn)

    # 2. Memory System
    runner.register_category("Memory System")
    for fn in [
        test_fail_phrases_exist,
        test_danger_phrases_exist,
        test_memory_extraction_patterns,
        test_memory_ranker_weights_sum,
        test_memory_category_boosts,
        test_memory_dedup_threshold,
        test_memory_max_per_category,
        test_memory_scoring_cosine_identical,
        test_memory_scoring_cosine_opposite,
    ]:
        runner.run_test("Memory System", fn.__doc__ or fn.__name__, fn)

    # 3. Tools --- Math
    runner.register_category("Tools --- Math")
    for fn in [
        test_calculator_basic_add,
        test_calculator_basic_multiply,
        test_calculator_divide_by_zero,
        test_calculator_all_operators,
        test_calculator_negative,
    ]:
        runner.run_test("Tools --- Math", fn.__doc__ or fn.__name__, fn)

    # 4. Tools --- File Operations
    runner.register_category("Tools --- File Ops")
    for fn in [
        test_file_write_and_read,
        test_file_write_protected_path,
        test_file_delete_protected_path,
        test_file_write_traversal_blocked,
        test_file_delete_traversal_blocked,
        test_file_edit_replace,
        test_file_grep,
        test_file_mkdir,
        test_file_append,
        test_file_read_range,
        test_file_delete,
        test_file_write_content_too_large,
        test_file_write_disabled,
        test_file_delete_disabled,
        test_file_protected_glob_key,
    ]:
        runner.run_test("Tools --- File Ops", fn.__doc__ or fn.__name__, fn)

    # 5. Tools --- Web
    runner.register_category("Tools --- Web")
    for fn in [
        test_web_search_tool_metadata,
        test_web_search_no_results,
        test_web_search_provider_error,
    ]:
        runner.run_test("Tools --- Web", fn.__doc__ or fn.__name__, fn)

    # 6. Tools --- System
    runner.register_category("Tools --- System")
    for fn in [
        test_shell_basic_command,
        test_shell_blocked_keyword,
        test_shell_blocked_extra_patterns,
        test_shell_disabled,
        test_system_info_tool,
        test_folder_tool_list,
    ]:
        runner.run_test("Tools --- System", fn.__doc__ or fn.__name__, fn)

    # 7. Tools --- Memory
    runner.register_category("Tools --- Memory")
    for fn in [
        test_memory_search_tool_metadata,
        test_memory_search_with_results,
        test_memory_search_empty,
    ]:
        runner.run_test("Tools --- Memory", fn.__doc__ or fn.__name__, fn)

    # 8. Agent System
    runner.register_category("Agent System")
    for fn in [
        test_agent_profile_create,
        test_agent_profile_serialization,
        test_agent_registry_default_exists,
        test_agent_registry_create,
        test_agent_registry_cannot_delete_default,
        test_agent_registry_set_model,
        test_agent_registry_set_persona,
        test_agent_tool_scoping,
        test_agent_tool_scoping_blocked,
    ]:
        runner.run_test("Agent System", fn.__doc__ or fn.__name__, fn)

    # 9. Brain & Routing
    runner.register_category("Brain & Routing")
    for fn in [
        test_tool_call_parser_json,
        test_tool_call_parser_null_tool,
        test_tool_call_parser_unknown_tool,
        test_tool_call_parser_markdown_fences,
        test_tool_call_parser_scoping,
        test_tool_result_formatter,
        test_base_tool_native_schema,
        test_tool_manager_native_schemas,
    ]:
        runner.run_test("Brain & Routing", fn.__doc__ or fn.__name__, fn)

    # 10. Agent Loop & Tool Calling
    runner.register_category("Agent Loop & Tool Calling")
    for fn in [
        test_agent_context_iteration_tracking,
        test_agent_context_history,
        test_agent_loop_max_iterations,
        test_native_tool_calling_flag,
        test_tool_manager_high_permission,
        test_tool_manager_validate_params_length,
        test_tool_manager_validate_unknown_tool,
    ]:
        runner.run_test("Agent Loop & Tool Calling", fn.__doc__ or fn.__name__, fn)

    # 11. Orchestration
    runner.register_category("Orchestration")
    for fn in [
        test_shared_context_set_get,
        test_shared_context_get_all,
        test_shared_context_clear,
        test_agent_message_task,
        test_agent_message_result,
        test_agent_message_serialization,
        test_orchestrator_delegate,
        test_orchestrator_delegate_agent_not_found,
    ]:
        runner.run_test("Orchestration", fn.__doc__ or fn.__name__, fn)

    # 12. Safety
    runner.register_category("Safety")
    for fn in [
        test_tool_manager_confirmation_accept,
        test_tool_manager_confirmation_reject,
        test_tool_manager_confirmation_skipped_for_low,
        test_tool_manager_audit_log,
        test_tool_manager_audit_log_disabled,
        test_file_write_protected_glob_pem,
        test_file_delete_protected_git,
    ]:
        runner.run_test("Safety", fn.__doc__ or fn.__name__, fn)

    # 13. Streaming
    runner.register_category("Streaming")
    for fn in [
        test_settings_streaming_default,
        test_settings_native_tool_calling_default,
        test_ollama_client_has_stream_methods,
        test_agent_loop_has_run_stream,
    ]:
        runner.run_test("Streaming", fn.__doc__ or fn.__name__, fn)

    # 14. Planner & Research
    runner.register_category("Planner & Research")
    for fn in [
        test_planner_create_plan,
        test_planner_summarize_plan,
        test_planner_analyze_plan,
        test_planner_returns_none_for_unknown,
        test_content_processor_clean,
        test_content_processor_empty,
        test_source_ranker_url_classification,
        test_report_generator,
    ]:
        runner.run_test("Planner & Research", fn.__doc__ or fn.__name__, fn)

    # 15. Live Integration Tests (only run with --live)
    runner.register_category("Live Integration")
    live_fns = [
        test_live_ollama_generate,
        test_live_ollama_chat,
        test_live_ollama_stream,
        test_live_calculator_then_llm,
        test_live_web_search,
        test_live_memory_store_and_search,
        test_live_full_agent_loop,
        test_live_agent_loop_stream,
    ]
    for fn in live_fns:
        runner.run_test("Live Integration", fn.__doc__ or fn.__name__, fn)


# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-
# MAIN
# -*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*--*-

def main():
    parser = argparse.ArgumentParser(description="AIKA Comprehensive Test Suite")
    parser.add_argument("--live", action="store_true", help="Run with real Ollama + PostgreSQL")
    parser.add_argument("--verbose", "-v", action="store_true", help="Show input/output details for each test")
    parser.add_argument("--category", type=str, help="Run only one category")
    parser.add_argument("--list", action="store_true", help="List all test categories")
    args = parser.parse_args()

    runner = AikaTestRunner(live_mode=args.live, verbose=args.verbose)

    # Register all tests (they execute immediately during registration)
    register_all_tests(runner)

    if args.list:
        runner.list_categories()
        return

    runner.run_all(category_filter=args.category)


if __name__ == "__main__":
    main()

