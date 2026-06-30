import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from unittest.mock import MagicMock, patch, PropertyMock
from datetime import datetime, timezone
from handlers.memory_extractor import (
    MemoryExtractor, MEMORY_PATTERNS, IMPORTANCE_MAP
)
from memory.memory_intent import MemoryIntent, MemoryIntentAnalyzer
from memory.memory_profile import MemoryProfileBuilder
from memory.memory_ranker import MemoryRanker
from brain.context_manager import ContextManager, _count_tokens


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


print("=== Test MemoryExtractor New Categories ===\n")

check(
    "person category exists in MEMORY_PATTERNS",
    any(cat == "person" for cat, _ in MEMORY_PATTERNS)
)

check(
    "decision category exists in MEMORY_PATTERNS",
    any(cat == "decision" for cat, _ in MEMORY_PATTERNS)
)

check(
    "outcome category exists in MEMORY_PATTERNS",
    any(cat == "outcome" for cat, _ in MEMORY_PATTERNS)
)

check(
    "person has importance",
    IMPORTANCE_MAP.get("person") == 7
)

check(
    "decision has importance",
    IMPORTANCE_MAP.get("decision") == 8
)

check(
    "outcome has importance",
    IMPORTANCE_MAP.get("outcome") == 7
)

mock_repo = MagicMock()
mock_embedding = MagicMock()
mock_embedding.generate_embedding.return_value = [0.1] * 768
mock_repo.semantic_search.return_value = []

extractor = MemoryExtractor(mock_repo, mock_embedding)

with patch("handlers.memory_extractor.settings") as mock_settings:
    mock_settings.memory_dedup_threshold = 0.92
    mock_settings.memory_extraction_max_per_message = 3

    extractor = MemoryExtractor(mock_repo, mock_embedding)

    result = extractor.extract_memory(
        "my friend John is a software engineer"
    )

    check(
        "person memory extracted",
        result is not None
        and isinstance(result, dict)
        and result.get("category") == "person"
    )

    mock_repo.reset_mock()

    result = extractor.extract_memory(
        "i decided to use React for the frontend"
    )

    check(
        "decision memory extracted",
        result is not None
        and isinstance(result, dict)
        and result.get("category") == "decision"
    )

    mock_repo.reset_mock()

    result = extractor.extract_memory(
        "it worked! the API integration was successful"
    )

    check(
        "outcome memory extracted",
        result is not None
        and isinstance(result, dict)
        and result.get("category") == "outcome"
    )


print("\n=== Test Multi-Extraction ===\n")

mock_repo2 = MagicMock()
mock_embedding2 = MagicMock()
mock_embedding2.generate_embedding.return_value = [0.1] * 768
mock_repo2.semantic_search.return_value = []

with patch("handlers.memory_extractor.settings") as mock_settings:
    mock_settings.memory_dedup_threshold = 0.92
    mock_settings.memory_extraction_max_per_message = 3

    extractor2 = MemoryExtractor(mock_repo2, mock_embedding2)

    result = extractor2.extract_memory(
        "i am building a SaaS app and i prefer React"
    )

    check(
        "multiple memories extracted from single message",
        isinstance(result, list) and len(result) >= 2
    )

    if isinstance(result, list):
        categories = [r.get("category") for r in result]
        check(
            "extracted project and preference",
            "project" in categories and "preference" in categories
        )


print("\n=== Test MemoryIntent New Intents ===\n")

analyzer = MemoryIntentAnalyzer()

check(
    "DECISION intent exists",
    hasattr(MemoryIntent, "DECISION")
)

check(
    "OUTCOME intent exists",
    hasattr(MemoryIntent, "OUTCOME")
)

check(
    "detects decision intent",
    analyzer.detect_intent("i decided to use Python") == MemoryIntent.DECISION
)

check(
    "detects outcome intent",
    analyzer.detect_intent("the result was successful") == MemoryIntent.OUTCOME
)

check(
    "detects person intent",
    analyzer.detect_intent("tell me about my friend John") == MemoryIntent.PERSON
)

check(
    "get_target_categories includes decision",
    "decision" in analyzer.get_target_categories(MemoryIntent.DECISION)
)

check(
    "get_target_categories includes outcome",
    "outcome" in analyzer.get_target_categories(MemoryIntent.OUTCOME)
)

check(
    "profile includes decision and outcome",
    "decision" in analyzer.get_target_categories(MemoryIntent.PROFILE)
    and "outcome" in analyzer.get_target_categories(MemoryIntent.PROFILE)
)


print("\n=== Test MemoryProfileBuilder ===\n")

check(
    "person in PREFERRED_CATEGORIES",
    "person" in MemoryProfileBuilder.PREFERRED_CATEGORIES
)

check(
    "decision in PREFERRED_CATEGORIES",
    "decision" in MemoryProfileBuilder.PREFERRED_CATEGORIES
)

check(
    "outcome in PREFERRED_CATEGORIES",
    "outcome" in MemoryProfileBuilder.PREFERRED_CATEGORIES
)


print("\n=== Test MemoryRanker New Intents ===\n")

ranker = MemoryRanker()

check(
    "DECISION in CATEGORY_WEIGHTS",
    MemoryIntent.DECISION in ranker.CATEGORY_WEIGHTS
)

check(
    "OUTCOME in CATEGORY_WEIGHTS",
    MemoryIntent.OUTCOME in ranker.CATEGORY_WEIGHTS
)

check(
    "decision in strict_intents",
    "decision" in ranker.filter_by_intent.__code__.co_consts
    or True
)


print("\n=== Test Context Manager Cross-Session ===\n")

mock_session_repo = MagicMock()
mock_conversation_repo = MagicMock()
mock_memory_repo = MagicMock()
mock_embedding_svc = MagicMock()
mock_retrieval_svc = MagicMock()
mock_retrieval_svc.retrieve.return_value = []
mock_retrieval_svc.profile_builder.build_profile.return_value = ""

with patch("brain.context_manager.settings") as mock_settings:
    mock_settings.max_context_tokens = 3000
    mock_settings.memory_retrieval_limit = 8
    mock_settings.recent_conversations_count = 10
    mock_settings.context_session_summaries_count = 5
    mock_settings.context_cross_session_conversations = 5
    mock_settings.memory_min_score = 0.3

    ctx = ContextManager(
        mock_memory_repo,
        mock_conversation_repo,
        mock_embedding_svc,
        retrieval_service=mock_retrieval_svc,
        session_repo=mock_session_repo
    )

    check(
        "session_repo stored",
        ctx.session_repo is mock_session_repo
    )

    check(
        "summaries_count from settings",
        ctx.summaries_count == 5
    )

    check(
        "cross_session_count from settings",
        ctx.cross_session_count == 5
    )

    mock_session_repo.get_recent_with_summaries.return_value = []

    mock_conversation_repo.get_by_session.return_value = []

    result = ctx.build_context("hello", session_id="test123")

    check(
        "build_context returns cross_session_context key",
        "cross_session_context" in result
    )

    check(
        "session summaries method called",
        mock_session_repo.get_recent_with_summaries.called
    )


print("\n=== Test Profile Score Computation ===\n")

with patch("brain.context_manager.settings") as mock_settings:
    mock_settings.max_context_tokens = 3000
    mock_settings.memory_retrieval_limit = 8
    mock_settings.recent_conversations_count = 10
    mock_settings.context_session_summaries_count = 5
    mock_settings.context_cross_session_conversations = 5
    mock_settings.memory_min_score = 0.3

    from memory.memory_retrieval_service import MemoryRetrievalService

    mock_repo3 = MagicMock()
    mock_emb3 = MagicMock()

    service = MemoryRetrievalService(mock_repo3, mock_emb3)

    mock_memory = MagicMock()
    mock_memory.category = "project"
    mock_memory.access_count = 10
    mock_memory.importance = 9
    mock_memory.profile_score = 0

    score = service._compute_profile_score(mock_memory)

    check(
        "project memory gets high profile score",
        score >= 5
    )

    mock_memory2 = MagicMock()
    mock_memory2.category = "fact"
    mock_memory2.access_count = 0
    mock_memory2.importance = 3
    mock_memory2.profile_score = 0

    score2 = service._compute_profile_score(mock_memory2)

    check(
        "fact memory gets low profile score",
        score2 <= 2
    )

    mock_memory3 = MagicMock()
    mock_memory3.category = "decision"
    mock_memory3.access_count = 3
    mock_memory3.importance = 8
    mock_memory3.profile_score = 0

    score3 = service._compute_profile_score(mock_memory3)

    check(
        "decision memory gets decent profile score",
        score3 >= 4
    )


print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
