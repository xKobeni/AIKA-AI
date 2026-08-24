import sys
from pathlib import Path
from unittest.mock import patch, MagicMock, call

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from memory.memory_retrieval_service import MemoryRetrievalService
from memory.memory_profile import MemoryProfileBuilder
from brain.context_manager import ContextManager
from handlers.memory_handler import MemoryHandler


class TestMemoryRetrievalServiceAgentId:

    def test_retrieve_passes_agent_id_to_semantic_search(self):
        mock_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.generate_embedding.return_value = [0.1, 0.2]
        mock_repo.semantic_search.return_value = []

        service = MemoryRetrievalService(mock_repo, mock_embedding)
        service.retrieve("test query", agent_id="agent_1")

        mock_repo.semantic_search.assert_called_once()
        call_kwargs = mock_repo.semantic_search.call_args
        assert call_kwargs[1].get("agent_id") == "agent_1"

    def test_retrieve_passes_none_agent_id_by_default(self):
        mock_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.generate_embedding.return_value = [0.1, 0.2]
        mock_repo.semantic_search.return_value = []

        service = MemoryRetrievalService(mock_repo, mock_embedding)
        service.retrieve("test query")

        call_kwargs = mock_repo.semantic_search.call_args
        assert call_kwargs[1].get("agent_id") is None

    def test_retrieve_profile_passes_agent_id(self):
        mock_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_builder = MagicMock()
        mock_builder.build_profile.return_value = ""

        service = MemoryRetrievalService(mock_repo, mock_embedding, profile_builder=mock_builder)
        service.retrieve_profile(agent_id="agent_2")

        mock_builder.build_profile.assert_called_once_with(agent_id="agent_2")


class TestMemoryProfileBuilderAgentId:

    def test_build_profile_passes_agent_id(self):
        mock_repo = MagicMock()
        mock_repo.get_top_profile_memories.return_value = []

        builder = MemoryProfileBuilder(mock_repo)
        builder.build_profile(agent_id="agent_3")

        mock_repo.get_top_profile_memories.assert_called_once()
        call_kwargs = mock_repo.get_top_profile_memories.call_args
        assert call_kwargs[1].get("agent_id") == "agent_3"
        assert call_kwargs[1].get("max_per_category") == 3


class TestContextManagerAgentId:

    def test_build_context_passes_agent_id_to_retrieval(self):
        mock_memory_repo = MagicMock()
        mock_conversation_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_retrieval = MagicMock()
        mock_retrieval.retrieve.return_value = []
        mock_retrieval.profile_builder.build_profile.return_value = ""
        mock_session_repo = MagicMock()
        mock_session_repo.get_recent_with_summaries.return_value = []

        ctx = ContextManager(
            mock_memory_repo,
            mock_conversation_repo,
            mock_embedding,
            retrieval_service=mock_retrieval,
            session_repo=mock_session_repo
        )
        ctx.build_context("hello", session_id="s1", agent_id="agent_4")

        mock_retrieval.retrieve.assert_called_once()
        call_kwargs = mock_retrieval.retrieve.call_args
        assert call_kwargs[1].get("agent_id") == "agent_4"

    def test_build_context_passes_agent_id_to_profile(self):
        mock_memory_repo = MagicMock()
        mock_conversation_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_retrieval = MagicMock()
        mock_retrieval.retrieve.return_value = []
        mock_retrieval.profile_builder.build_profile.return_value = ""
        mock_session_repo = MagicMock()
        mock_session_repo.get_recent_with_summaries.return_value = []

        ctx = ContextManager(
            mock_memory_repo,
            mock_conversation_repo,
            mock_embedding,
            retrieval_service=mock_retrieval,
            session_repo=mock_session_repo
        )
        ctx.build_context("hello", session_id="s1", agent_id="agent_5")

        mock_retrieval.profile_builder.build_profile.assert_called_once()
        call_kwargs = mock_retrieval.profile_builder.build_profile.call_args
        assert call_kwargs[1].get("agent_id") == "agent_5"


class TestMemoryHandlerAgentId:

    def test_store_memory_passes_agent_id(self):
        mock_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_embedding.generate_embedding.return_value = [0.1, 0.2]

        handler = MemoryHandler(mock_repo, mock_embedding)
        handler.store_memory("remember project: test", agent_id="agent_6")

        mock_repo.create.assert_called_once()
        call_kwargs = mock_repo.create.call_args
        assert call_kwargs[1].get("agent_id") == "agent_6"

    def test_list_memories_passes_agent_id(self):
        mock_repo = MagicMock()
        mock_repo.get_all.return_value = []
        mock_embedding = MagicMock()

        handler = MemoryHandler(mock_repo, mock_embedding)
        handler.list_memories(agent_id="agent_7")

        mock_repo.get_all.assert_called_once_with(agent_id="agent_7")

    def test_search_memory_passes_agent_id_to_retrieval(self):
        mock_repo = MagicMock()
        mock_embedding = MagicMock()
        mock_retrieval = MagicMock()
        mock_retrieval.retrieve.return_value = []

        handler = MemoryHandler(mock_repo, mock_embedding, retrieval_service=mock_retrieval)
        handler.search_memory("test", agent_id="agent_8")

        mock_retrieval.retrieve.assert_called_once()
        call_kwargs = mock_retrieval.retrieve.call_args
        assert call_kwargs[1].get("agent_id") == "agent_8"
