from config.settings import settings
from planner.plan import Plan
from planner.plan_step import PlanStep


class ExecutionPlanner:

    def __init__(self):
        self.web_search_max_results = settings.plan_web_search_max_results

    def refresh_from_settings(self):
        self.web_search_max_results = settings.plan_web_search_max_results

    RESEARCH_PREFIXES = [
        "research ", "learn about ",
        "investigate ", "study ",
        "find information about "
    ]

    SEARCH_PREFIXES = [
        "find and read ", "find and ",
        "search and read ", "search and ",
        "find ", "search for "
    ]

    READ_PREFIXES = [
        "read and summarize ",
        "read and ", "read "
    ]

    def create_plan(
        self,
        user_message: str
    ):

        text = user_message.lower().strip()

        has_summarize = "summarize" in text
        has_analyze = any(
            w in text
            for w in ["analyze", "review", "inspect", "research", "investigate"]
        )
        has_file_search = any(
            p in text
            for p in self.SEARCH_PREFIXES
        )
        has_read = any(
            p in text
            for p in self.READ_PREFIXES
        )
        has_memory = any(
            w in text
            for w in ["memory", "memories"]
        )

        has_research = any(
            p in text
            for p in self.RESEARCH_PREFIXES
        )

        needs_summary = has_summarize or has_analyze

        query = self._extract_query(text)

        # Workflow: research topic
        if has_research:

            search_query = self._extract_search_query(
                text,
                self.RESEARCH_PREFIXES
            )

            return Plan(
                goal="research_report",
                steps=[
                    PlanStep(
                        1,
                        "web_search",
                        {
                            "query": search_query,
                            "max_results": self.web_search_max_results
                        },
                        "Search the web"
                    ),
                    PlanStep(
                        2,
                        "web_crawl",
                        {},
                        "Crawl top results"
                    ),
                    PlanStep(
                        3,
                        "content_process",
                        {},
                        "Process and combine content"
                    ),
                    PlanStep(
                        4,
                        "summarize",
                        {},
                        "Summarize research findings"
                    ),
                    PlanStep(
                        5,
                        "generate_report",
                        {},
                        "Generate structured report"
                    )
                ]
            )

        # Workflow: read and summarize (direct file read + summarize)
        if needs_summary and has_read and not has_file_search:

            file_path = self._extract_file_path(
                text,
                self.READ_PREFIXES
            )

            if file_path:

                return Plan(
                    goal="summarize",
                    steps=[
                        PlanStep(
                            1,
                            "file_read",
                            {"file_path": file_path},
                            "Read the file"
                        ),
                        PlanStep(
                            2,
                            "summarize",
                            {},
                            "Summarize the content"
                        )
                    ]
                )

        # Workflow: summarize/analyze a general topic via web search
        if needs_summary and not has_file_search and not has_read and not has_memory and not self._looks_like_file(query):

            return Plan(
                goal="summarize",
                steps=[
                    PlanStep(
                        1,
                        "web_search",
                        {
                            "query": query,
                            "max_results": self.web_search_max_results
                        },
                        "Search the web"
                    ),
                    PlanStep(
                        2,
                        "summarize",
                        {},
                        "Summarize findings"
                    )
                ]
            )

        # Workflow: summarize/analyze with file search
        if needs_summary and (has_file_search or not has_memory):

            if has_file_search:
                search_query = self._extract_search_query(
                    text,
                    self.SEARCH_PREFIXES
                )
            else:
                search_query = self._extract_query(text)

            return Plan(
                goal="summarize",
                steps=[
                    PlanStep(
                        1,
                        "file_search",
                        {"query": search_query},
                        "Search for file"
                    ),
                    PlanStep(
                        2,
                        "file_read",
                        {},
                        "Read the found file"
                    ),
                    PlanStep(
                        3,
                        "summarize",
                        {},
                        "Summarize the content"
                    )
                ]
            )

        # Workflow: summarize/analyze with memory reference
        if needs_summary and has_memory:

            return Plan(
                goal="summarize_memories",
                steps=[
                    PlanStep(
                        1,
                        "memory_search",
                        {"query": query},
                        "Search memories"
                    ),
                    PlanStep(
                        2,
                        "summarize",
                        {},
                        "Summarize memories"
                    )
                ]
            )

        # Workflow: find file and read it
        if has_file_search:

            search_query = self._extract_search_query(
                text,
                self.SEARCH_PREFIXES
            )

            return Plan(
                goal="find_and_read",
                steps=[
                    PlanStep(
                        1,
                        "file_search",
                        {"query": search_query},
                        "Search for file"
                    ),
                    PlanStep(
                        2,
                        "file_read",
                        {},
                        "Read the found file"
                    )
                ]
            )

        # Workflow: read file directly
        if has_read:

            file_path = self._extract_file_path(
                text,
                self.READ_PREFIXES
            )

            if file_path:

                return Plan(
                    goal="find_and_read",
                    steps=[
                        PlanStep(
                            1,
                            "file_read",
                            {"file_path": file_path},
                            "Read the file"
                        )
                    ]
                )

        return None

    FILE_EXTENSIONS = [
        ".py", ".md", ".txt", ".json", ".yaml", ".yml",
        ".toml", ".cfg", ".ini", ".csv", ".xml", ".html",
        ".css", ".js", ".ts", ".jsx", ".tsx", ".vue",
        ".c", ".cpp", ".h", ".hpp", ".java", ".rs", ".go",
        ".rb", ".php", ".sh", ".bat", ".ps1", ".sql",
        ".env", ".gitignore", ".dockerfile", ".lock",
    ]

    def _looks_like_file(self, query):
        for ext in self.FILE_EXTENSIONS:
            if ext in query:
                return True
        if "/" in query or "\\" in query:
            return True
        return False

    def _extract_search_query(
        self,
        text,
        prefixes
    ):

        for prefix in prefixes:
            if text.startswith(prefix):
                return text[len(prefix):].strip()

        return text.strip()

    def _extract_file_path(
        self,
        text,
        prefixes
    ):

        for prefix in prefixes:
            if text.startswith(prefix):
                rest = text[len(prefix):].strip()
                if rest:
                    return rest

        return ""

    def _extract_query(
        self,
        text
    ):

        for stop_word in [
            "summarize", "analyze", "review", "inspect",
            "research", "investigate", "find", "search for",
            "read", "my", "about", "and"
        ]:
            text = text.replace(stop_word, "")

        return text.strip()
