from enum import Enum


class MemoryIntent(Enum):
    GENERAL = "general"
    GOAL = "goal"
    PROJECT = "project"
    PREFERENCE = "preference"
    SKILL = "skill"
    PERSON = "person"
    FACT = "fact"
    PROFILE = "profile"
    DECISION = "decision"
    OUTCOME = "outcome"


class MemoryIntentAnalyzer:

    INTENT_PATTERNS = {
        MemoryIntent.GOAL: [
            "goal", "goals", "objective", "objectives",
            "want to achieve", "target", "aim",
            "trying to do", "working toward"
        ],
        MemoryIntent.PROJECT: [
            "project", "projects", "building", "working on",
            "developing", "creating", "making"
        ],
        MemoryIntent.PREFERENCE: [
            "prefer", "preferences", "preference",
            "like", "likes", "favorite", "favourite",
            "hobby", "hobbies", "interest", "interests"
        ],
        MemoryIntent.SKILL: [
            "skill", "skills", "good at", "experience",
            "know how", "proficient", "expert"
        ],
        MemoryIntent.PERSON: [
            "family", "friend", "friends", "person",
            "people", "know about", "tell me about"
        ],
        MemoryIntent.DECISION: [
            "decided", "chose", "chosen", "agreed",
            "settled on", "went with", "decision"
        ],
        MemoryIntent.OUTCOME: [
            "result", "outcome", "worked", "failed",
            "learned", "turned out", "succeeded"
        ],
    }

    PROFILE_PHRASES = [
        "what do you know about me",
        "tell me about me",
        "tell me about myself",
        "summarize me",
        "what do you remember about me",
        "what information do you have about me",
        "who am i",
    ]

    def detect_intent(self, query):
        if not query:
            return MemoryIntent.GENERAL

        query_lower = query.lower().strip()

        for phrase in self.PROFILE_PHRASES:
            if phrase in query_lower:
                return MemoryIntent.PROFILE

        for intent, patterns in self.INTENT_PATTERNS.items():
            for pattern in patterns:
                if pattern in query_lower:
                    return intent

        return MemoryIntent.GENERAL

    def get_target_categories(self, intent):
        mapping = {
            MemoryIntent.GOAL: ["goal"],
            MemoryIntent.PROJECT: ["project"],
            MemoryIntent.PREFERENCE: ["preference"],
            MemoryIntent.SKILL: ["skill"],
            MemoryIntent.PERSON: ["person"],
            MemoryIntent.FACT: ["fact"],
            MemoryIntent.DECISION: ["decision"],
            MemoryIntent.OUTCOME: ["outcome"],
            MemoryIntent.PROFILE: [
                "project", "goal", "preference",
                "skill", "person", "decision", "outcome"
            ],
            MemoryIntent.GENERAL: [],
        }

        return mapping.get(intent, [])
