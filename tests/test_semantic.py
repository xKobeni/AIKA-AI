import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from llm.embedding_service import EmbeddingService
from repositories.memory_repository import MemoryRepository


class TestSemanticSearch:

    def test_generate_embedding_returns_list(self):
        mock_response = {"embeddings": [[0.1] * 768]}
        with patch("llm.embedding_service.ollama.embed", return_value=mock_response):
            service = EmbeddingService()
            result = service.generate_embedding("What language is AIKA built with?")
            assert isinstance(result, list)
            assert len(result) == 768

    def test_semantic_search_returns_list(self):
        mock_memory = MagicMock()
        mock_memory.content = "AIKA is built with Python"
        mock_memory._score = 0.85

        repo = MemoryRepository()
        with patch.object(repo, "semantic_search", return_value=[mock_memory]):
            results = repo.semantic_search([0.1] * 768, limit=5)
            assert isinstance(results, list)
            assert len(results) == 1
            assert results[0].content == "AIKA is built with Python"

    def test_semantic_search_empty_when_no_match(self):
        repo = MemoryRepository()
        with patch.object(repo, "semantic_search", return_value=[]):
            results = repo.semantic_search([0.1] * 768, limit=5)
            assert results == []

    def test_embedding_service_returns_none_on_empty(self):
        service = EmbeddingService()
        result = service.generate_embedding("")
        assert result is None

    def test_embedding_service_returns_none_on_whitespace(self):
        service = EmbeddingService()
        result = service.generate_embedding("   ")
        assert result is None
