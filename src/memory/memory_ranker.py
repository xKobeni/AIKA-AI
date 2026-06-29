from memory.memory_intent import MemoryIntent
from config.settings import settings


class MemoryRanker:

    CATEGORY_WEIGHTS = {
        MemoryIntent.GOAL: {"goal": 3.0},
        MemoryIntent.PROJECT: {"project": 3.0},
        MemoryIntent.PREFERENCE: {"preference": 3.0},
        MemoryIntent.SKILL: {"skill": 2.5},
        MemoryIntent.PERSON: {"person": 2.5},
        MemoryIntent.FACT: {"fact": 1.5},
        MemoryIntent.GENERAL: {},
    }

    MAX_PER_CATEGORY = settings.memory_max_per_category

    def rank(self, memories, intent):
        if not memories:
            return []

        weights = self.CATEGORY_WEIGHTS.get(intent, {})

        scored = []

        for memory in memories:
            score = getattr(memory, "_score", 0.0)
            boost = weights.get(memory.category, 1.0)
            scored.append((memory, score * boost))

        scored.sort(key=lambda x: x[1], reverse=True)

        return [m for m, s in scored]

    def filter_by_intent(self, memories, intent):
        if not memories:
            return []

        strict_intents = {
            MemoryIntent.GOAL: "goal",
            MemoryIntent.PROJECT: "project",
            MemoryIntent.PREFERENCE: "preference",
            MemoryIntent.SKILL: "skill",
            MemoryIntent.PERSON: "person",
        }

        target = strict_intents.get(intent)

        if target is None:
            return memories

        filtered = [
            m for m in memories
            if m.category == target
        ]

        if filtered:
            return filtered

        return memories

    def apply_diversity(self, memories, max_per_category=None):
        if not memories:
            return []

        if max_per_category is None:
            max_per_category = self.MAX_PER_CATEGORY

        seen = {}
        result = []

        for memory in memories:
            cat = memory.category
            count = seen.get(cat, 0)

            if count < max_per_category:
                result.append(memory)
                seen[cat] = count + 1

        return result
