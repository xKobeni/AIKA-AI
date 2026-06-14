class ReportGenerator:

    def __init__(
        self,
        llm
    ):

        self.llm = llm

    def generate(
        self,
        query,
        content,
        summary="",
        citations=None
    ):

        citations_section = ""

        if citations:

            lines = []

            for i, c in enumerate(citations):

                title = c.get("title", f"Source {i + 1}")
                url = c.get("url", "")
                source_type = c.get("source_type", "")

                line = f"{i + 1}. {title}"

                if source_type:
                    line += f" ({source_type})"

                if url:
                    line += f"\n   {url}"

                lines.append(line)

            citations_section = (
                "\n\nSources consulted:\n\n" + "\n\n".join(lines)
            )

        prompt = f"""
            Generate a structured research report
            based on the following findings.

            Research Topic:
            {query}

            Research Content:
            {content}

            Summary:
            {summary}
            {citations_section}

            Format the report with these sections:

            ## Overview
            ## Key Features
            ## Advantages
            ## Limitations
            ## Use Cases
            ## Important Technical Details
            ## Sources

            Be thorough and informative.
            Use the research content only.
            Do not invent information.
            When citing specific claims in the report, reference
            the source number from the Sources section.
            """

        report = self.llm.generate(prompt)

        return report
