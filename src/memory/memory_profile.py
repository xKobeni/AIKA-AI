class MemoryProfileBuilder:

    PREFERRED_CATEGORIES = [
        "project", "goal", "preference", "skill",
        "person", "decision", "outcome"
    ]

    def __init__(self, memory_repo):

        self.memory_repo = memory_repo

    def build_profile(self, max_per_category=None, agent_id=None):
        if max_per_category is None:
            max_per_category = 3

        all_memories = self.memory_repo.get_top_profile_memories(
            self.PREFERRED_CATEGORIES,
            max_per_category=max_per_category,
            agent_id=agent_id
        )

        categories = {}

        for cat in self.PREFERRED_CATEGORIES:
            cat_mems = [
                m for m in all_memories
                if m.category == cat
            ]

            if cat_mems:
                categories[cat] = cat_mems[:max_per_category]

        lines = []

        for cat in self.PREFERRED_CATEGORIES:
            mems = categories.get(cat, [])

            if mems:
                label = cat.capitalize()

                items = "\n".join(
                    f"  - {mem.content}"
                    for mem in mems
                )

                lines.append(f"{label}:\n{items}")

        return "\n\n".join(lines) if lines else ""

    def format_profile_section(self, profile_text):
        if not profile_text:
            return ""

        return (
            "Information I know about you:\n"
            f"{profile_text}"
        )
