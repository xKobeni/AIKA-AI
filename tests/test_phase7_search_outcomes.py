import logging
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from brain.agent_loop import AgentLoop
from handlers.tool_handler import ToolHandler
from models.tool_request import ToolRequest
from research import DDGSProvider, SearchProviderError
from tools.tool_manager import ToolManager
from tools.web_search_tool import (
    NO_RESULTS_MESSAGE,
    PROVIDER_UNAVAILABLE_MESSAGE,
    SEARCH_OUTCOME_NO_RESULTS,
    SEARCH_OUTCOME_PROVIDER_ERROR,
    WebSearchTool,
)


class EmptyProvider:
    def search(self, query, max_results=5):
        return []


class TypedFailingProvider:
    def search(self, query, max_results=5):
        raise SearchProviderError("TimeoutError", provider="test")


class UnexpectedFailingProvider:
    def search(self, query, max_results=5):
        raise RuntimeError("private backend detail")


def _loop_with_result(result):
    manager = ToolManager()
    manager._audit_log = Mock()
    tool = WebSearchTool()
    tool.execute = Mock(return_value=result)
    manager.register_tool(tool)
    llm = Mock()
    llm._uses_configured_client = True
    loop = AgentLoop(
        decision_engine=Mock(),
        router=Mock(),
        llm=llm,
        tool_manager=manager,
        llm_tool_router=object(),
    )
    loop.max_iterations = 3
    return loop, llm, tool


def test_empty_provider_response_is_a_genuine_zero_result():
    result = WebSearchTool(provider=EmptyProvider()).execute("missing title")

    assert result == {
        "success": True,
        "outcome": SEARCH_OUTCOME_NO_RESULTS,
        "results": [],
        "message": NO_RESULTS_MESSAGE,
    }


@pytest.mark.parametrize(
    ("provider", "error_type"),
    [
        (TypedFailingProvider(), "TimeoutError"),
        (UnexpectedFailingProvider(), "RuntimeError"),
    ],
)
def test_provider_failures_are_unavailable_and_sanitized(
    provider, error_type, caplog
):
    with caplog.at_level(logging.WARNING):
        result = WebSearchTool(provider=provider).execute("private query")

    assert result == {
        "success": False,
        "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
        "results": [],
        "error": PROVIDER_UNAVAILABLE_MESSAGE,
        "error_type": error_type,
    }
    assert "private backend detail" not in str(result)
    assert "private backend detail" not in caplog.text
    assert error_type in caplog.text


def test_ddgs_provider_raises_typed_error_without_printing_sensitive_detail(
    caplog,
):
    class FakeDDGS:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def text(self, query, max_results=5):
            raise TimeoutError("private DDGS response detail")

    fake_module = SimpleNamespace(DDGS=FakeDDGS)
    with (
        patch.dict(sys.modules, {"ddgs": fake_module}),
        patch("builtins.print") as print_mock,
        caplog.at_level(logging.WARNING),
        pytest.raises(SearchProviderError) as raised,
    ):
        DDGSProvider().search("private query")

    assert raised.value.error_type == "TimeoutError"
    assert raised.value.provider == "ddgs"
    print_mock.assert_not_called()
    assert "TimeoutError" in caplog.text
    assert "private DDGS response detail" not in caplog.text


def test_typed_provider_error_rejects_unsafe_log_classification():
    error = SearchProviderError(
        "TimeoutError: private detail",
        provider="private provider detail",
    )

    assert error.error_type == "SearchProviderError"
    assert error.provider == "search"
    assert "private detail" not in str(error)


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            {
                "success": True,
                "outcome": SEARCH_OUTCOME_NO_RESULTS,
                "results": [],
                "message": NO_RESULTS_MESSAGE,
            },
            NO_RESULTS_MESSAGE,
        ),
        (
            {
                "success": False,
                "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
                "results": [],
                "error": PROVIDER_UNAVAILABLE_MESSAGE,
                "error_type": "TimeoutError",
            },
            PROVIDER_UNAVAILABLE_MESSAGE,
        ),
    ],
)
def test_terminal_search_outcomes_are_visible_once_without_llm_or_retry(
    result, expected
):
    loop, llm, tool = _loop_with_result(result)

    response = "".join(loop.run_stream(
        "search for a movie",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "a movie"}
        ),
    ))

    assert response == expected
    assert tool.execute.call_count == 1
    assert loop.last_iterations == 1
    llm.chat.assert_not_called()


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            {
                "success": True,
                "outcome": SEARCH_OUTCOME_NO_RESULTS,
                "results": [],
                "message": NO_RESULTS_MESSAGE,
            },
            NO_RESULTS_MESSAGE,
        ),
        (
            {
                "success": False,
                "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
                "results": [],
                "error": PROVIDER_UNAVAILABLE_MESSAGE,
            },
            PROVIDER_UNAVAILABLE_MESSAGE,
        ),
    ],
)
def test_sync_terminal_search_outcomes_are_visible_without_llm(result, expected):
    loop, llm, tool = _loop_with_result(result)

    response = loop.run(
        "search for a movie",
        initial_tool_request=ToolRequest(
            "web_search", {"query": "a movie"}
        ),
    )

    assert response == expected
    assert tool.execute.call_count == 1
    assert loop.last_iterations == 1
    llm.chat.assert_not_called()


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        (
            {
                "success": True,
                "outcome": SEARCH_OUTCOME_NO_RESULTS,
                "results": [],
                "message": NO_RESULTS_MESSAGE,
            },
            NO_RESULTS_MESSAGE,
        ),
        (
            {
                "success": False,
                "outcome": SEARCH_OUTCOME_PROVIDER_ERROR,
                "results": [],
                "error": PROVIDER_UNAVAILABLE_MESSAGE,
            },
            PROVIDER_UNAVAILABLE_MESSAGE,
        ),
    ],
)
def test_legacy_tool_handler_does_not_ask_llm_to_reinterpret_terminal_outcome(
    result, expected
):
    manager = Mock()
    manager.execute_tool.return_value = result
    response_handler = Mock()
    handler = ToolHandler(manager, response_handler)

    response = handler.handle(
        ToolRequest("web_search", {"query": "a movie"})
    )

    assert response == expected
    response_handler.generate_response.assert_not_called()
