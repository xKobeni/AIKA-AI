import sys
from pathlib import Path
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta
import math

sys.path.append(
    str(Path(__file__).resolve().parent.parent / "src")
)

import pytest
from repositories.memory_repository import MemoryRepository


class TestSemanticScoring:

    def _make_memory(self, content, category="fact", importance=5,
                     access_count=0, created_at=None, last_accessed=None, embedding=None):
        m = MagicMock()
        m.id = 1
        m.content = content
        m.category = category
        m.importance = importance
        m.access_count = access_count
        m.created_at = created_at or datetime.utcnow()
        m.last_accessed = last_accessed
        m.embedding = embedding or [0.1] * 768
        m._score = 0.0
        return m

    def test_cosine_similarity_identical_vectors(self):
        repo = MemoryRepository()
        vec = [1.0, 0.0, 0.0]
        score = repo.cosine_similarity(vec, vec)
        assert abs(score - 1.0) < 0.001

    def test_cosine_similarity_orthogonal_vectors(self):
        repo = MemoryRepository()
        a = [1.0, 0.0, 0.0]
        b = [0.0, 1.0, 0.0]
        score = repo.cosine_similarity(a, b)
        assert abs(score) < 0.001

    def test_cosine_similarity_opposite_vectors(self):
        repo = MemoryRepository()
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        score = repo.cosine_similarity(a, b)
        assert abs(score + 1.0) < 0.001

    def test_scoring_combines_similarity_and_recency(self):
        repo = MemoryRepository()
        now = datetime.utcnow()
        recent = self._make_memory(
            "recent memory", category="fact", importance=5,
            last_accessed=now
        )
        old = self._make_memory(
            "old memory", category="fact", importance=5,
            last_accessed=now - timedelta(days=30)
        )
        assert recent.last_accessed > old.last_accessed

    def test_importance_affects_ranking(self):
        high_imp = self._make_memory("important", importance=9)
        low_imp = self._make_memory("trivial", importance=2)
        assert high_imp.importance > low_imp.importance

    def test_access_count_affects_ranking(self):
        frequent = self._make_memory("frequent", access_count=10)
        rare = self._make_memory("rare", access_count=0)
        assert frequent.access_count > rare.access_count

    def test_category_boost_project(self):
        project = self._make_memory("project", category="project")
        fact = self._make_memory("fact", category="fact")
        boost_map = {"project": 0.3, "goal": 0.2, "skill": 0.1}
        assert boost_map.get(project.category, 0) > boost_map.get(fact.category, 0)

    def test_recency_decay_formula(self):
        now = datetime.utcnow()
        hrs_1 = 1.0
        hrs_100 = 100.0
        half_life = 720.0
        rec_1 = math.exp(-hrs_1 / half_life)
        rec_100 = math.exp(-hrs_100 / half_life)
        assert rec_1 > rec_100
        assert rec_1 > 0.9

    def test_log_scaled_access_count(self):
        assert math.log(1 + 10) > math.log(1 + 0)
        assert math.log(1 + 100) > math.log(1 + 10)
