import pytest
from unittest.mock import patch, MagicMock


class TestOllamaClientStreaming:

    def test_generate_stream_returns_iterator(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "Hello"}},
                {"message": {"content": " world"}},
            ])
            result = client.generate_stream("test prompt")
            assert hasattr(result, "__iter__")

    def test_generate_stream_yields_chunks(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "Hello"}},
                {"message": {"content": " world"}},
            ])
            chunks = list(client.generate_stream("test prompt"))
            assert chunks == ["Hello", " world"]

    def test_generate_stream_yields_all_chunks(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "Hello"}},
                {"message": {"content": ""}},
                {"message": {"content": " world"}},
            ])
            chunks = list(client.generate_stream("test prompt"))
            assert chunks == ["Hello", "", " world"]

    def test_chat_stream_returns_iterator(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "Hi"}},
            ])
            messages = [{"role": "user", "content": "hello"}]
            result = client.chat_stream(messages)
            assert hasattr(result, "__iter__")

    def test_chat_stream_yields_chunks(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "A"}},
                {"message": {"content": "B"}},
                {"message": {"content": "C"}},
            ])
            messages = [{"role": "user", "content": "test"}]
            chunks = list(client.chat_stream(messages))
            assert chunks == ["A", "B", "C"]

    def test_generate_stream_passes_model(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "ok"}},
            ])
            list(client.generate_stream("test", model="custom:model"))
            mock_ollama.chat.assert_called_once()
            call_kwargs = mock_ollama.chat.call_args
            assert call_kwargs[1]["model"] == "custom:model"

    def test_generate_stream_passes_stream_true(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "ok"}},
            ])
            list(client.generate_stream("test"))
            call_kwargs = mock_ollama.chat.call_args
            assert call_kwargs[1]["stream"] is True

    def test_chat_stream_passes_stream_true(self):
        from llm.ollama_client import OllamaClient
        client = OllamaClient()
        with patch("llm.ollama_client.ollama") as mock_ollama:
            mock_ollama.chat.return_value = iter([
                {"message": {"content": "ok"}},
            ])
            list(client.chat_stream([{"role": "user", "content": "hi"}]))
            call_kwargs = mock_ollama.chat.call_args
            assert call_kwargs[1]["stream"] is True


class TestSettingsStreaming:

    def test_streaming_enabled_default(self):
        from config.settings import Settings
        with patch.dict("os.environ", {}, clear=False):
            s = Settings()
            assert hasattr(s, "streaming_enabled")
            assert isinstance(s.streaming_enabled, bool)

    def test_native_tool_calling_default(self):
        from config.settings import Settings
        with patch.dict("os.environ", {}, clear=False):
            s = Settings()
            assert hasattr(s, "native_tool_calling")
            assert isinstance(s.native_tool_calling, bool)
