import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from llm.embedding_service import EmbeddingService


class TestEmbeddingService:

    def test_generate_embedding_returns_vector(self):
        mock_response = {"embeddings": [[0.1, 0.2, 0.3, 0.4, 0.5]]}
        with patch("llm.embedding_service.ollama.embed", return_value=mock_response):
            service = EmbeddingService()
            result = service.generate_embedding("AIKA is built with Python")
            assert result is not None
            assert len(result) == 5
            assert result == [0.1, 0.2, 0.3, 0.4, 0.5]

    def test_generate_embedding_empty_text_returns_none(self):
        service = EmbeddingService()
        result = service.generate_embedding("")
        assert result is None

    def test_generate_embedding_whitespace_only_returns_none(self):
        service = EmbeddingService()
        result = service.generate_embedding("   ")
        assert result is None

    def test_generate_embedding_no_embeddings_key_returns_none(self):
        with patch("llm.embedding_service.ollama.embed", return_value={}):
            service = EmbeddingService()
            result = service.generate_embedding("test text")
            assert result is None

    def test_generate_embedding_empty_embeddings_returns_none(self):
        with patch("llm.embedding_service.ollama.embed", return_value={"embeddings": []}):
            service = EmbeddingService()
            result = service.generate_embedding("test text")
            assert result is None

    def test_generate_embedding_connection_error_returns_none(self):
        with patch("llm.embedding_service.ollama.embed", side_effect=ConnectionError("connection refused")):
            service = EmbeddingService()
            result = service.generate_embedding("test text")
            assert result is None

    def test_generate_embedding_model_error_returns_none(self):
        import ollama
        with patch("llm.embedding_service.ollama.embed", side_effect=ollama.ResponseError("model not found")):
            service = EmbeddingService()
            result = service.generate_embedding("test text")
            assert result is None

    def test_generate_embedding_generic_exception_returns_none(self):
        with patch("llm.embedding_service.ollama.embed", side_effect=RuntimeError("unexpected")):
            service = EmbeddingService()
            result = service.generate_embedding("test text")
            assert result is None
