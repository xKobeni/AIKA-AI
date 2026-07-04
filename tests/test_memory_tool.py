import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from tools.memory_search_tool import MemorySearchTool


class TestMemorySearchTool:

    def test_tool_metadata(self):
        tool = MemorySearchTool(retrieval_service=MagicMock())
        assert tool.name == "memory_search"
        assert "memor" in tool.description.lower()

    def test_search_with_mock_service(self):
        mock_service = MagicMock()
        mock_service.retrieve.return_value = [
            MagicMock(content="User fact: I live in Tokyo"),
            MagicMock(content="User goal: build an AI assistant"),
        ]
        tool = MemorySearchTool(retrieval_service=mock_service)
        result = tool.execute(query="AIKA")
        assert result is not None
        mock_service.retrieve.assert_called_once()

    def test_search_with_string_result(self):
        mock_service = MagicMock()
        mock_service.retrieve.return_value = "No memories found."
        tool = MemorySearchTool(retrieval_service=mock_service)
        result = tool.execute(query="nonexistent")
        assert result is not None

    def test_search_with_empty_result(self):
        mock_service = MagicMock()
        mock_service.retrieve.return_value = []
        tool = MemorySearchTool(retrieval_service=mock_service)
        result = tool.execute(query="nothing")
        assert result is not None

    def test_search_returns_dict_with_success(self):
        mock_service = MagicMock()
        mock_service.retrieve.return_value = [
            MagicMock(content="test memory"),
        ]
        tool = MemorySearchTool(retrieval_service=mock_service)
        result = tool.execute(query="test")
        assert isinstance(result, dict)
        assert result.get("success") is True
