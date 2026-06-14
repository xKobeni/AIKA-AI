class ContentProcessor:

    def process(
        self,
        pages
    ):

        if not pages:
            return ""

        combined = self._combine(pages)

        combined = self._deduplicate(combined)

        combined = self._clean(combined)

        return combined

    def _combine(
        self,
        pages
    ):

        sections = []

        for i, page in enumerate(pages):

            content = (
                page.get("content", "")
                if isinstance(page, dict)
                else str(page)
            )

            if content.strip():

                sections.append(
                    f"--- Source {i + 1} ---\n{content}"
                )

        return "\n\n".join(sections)

    def _deduplicate(
        self,
        text
    ):

        seen = set()
        lines = text.splitlines()
        unique = []

        for line in lines:

            stripped = line.strip().lower()

            if stripped and stripped not in seen:

                seen.add(stripped)
                unique.append(line)

            elif not stripped:

                unique.append(line)

        return "\n".join(unique)

    def _clean(
        self,
        text
    ):

        import re

        text = re.sub(
            r"\n{3,}",
            "\n\n",
            text
        )

        text = re.sub(
            r" {2,}",
            " ",
            text
        )

        return text.strip()
