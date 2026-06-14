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
        summary=""
    ):

        prompt = f"""
            Generate a structured research report
            based on the following findings.

            Research Topic:
            {query}

            Research Content:
            {content}

            Summary:
            {summary}

            Format the report with these sections:

            ## Overview
            ## Key Features
            ## Advantages
            ## Limitations
            ## Use Cases
            ## Important Technical Details

            Be thorough and informative.
            Use the research content only.
            Do not invent information.
            """

        report = self.llm.generate(prompt)

        return report
