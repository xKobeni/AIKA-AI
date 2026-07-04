import logging
from datetime import datetime

from config.settings import settings
from planner.execution_context import ExecutionContext
from research.content_processor import ContentProcessor
from research.report_generator import ReportGenerator
from research.source_ranker import SourceRanker

logger = logging.getLogger(__name__)


class PlanExecutor:

    def __init__(
        self,
        tool_manager,
        llm
    ):

        self.tool_manager = tool_manager
        self.llm = llm
        self.content_processor = ContentProcessor()
        self.report_generator = ReportGenerator(llm)
        self.source_ranker = SourceRanker()
        self.log_path = settings.execution_log_path
        self.top_sources_count = settings.plan_top_sources_count

    def execute_plan(
        self,
        plan
    ):

        context = ExecutionContext()
        goal = plan.goal
        steps = plan.steps

        self._log(
            f"Plan start | goal={goal} | steps={[s.tool_name for s in steps]}"
        )

        start_time = datetime.now()

        for step in steps:

            step_start = datetime.now()

            logger.debug(
                "Step %d: %s - %s",
                step.step_id, step.tool_name, step.description
            )

            try:

                if step.tool_name == "summarize":

                    result = self._run_summarize(context)

                elif step.tool_name in (
                    "content_process",
                    "generate_report"
                ):

                    result = {"success": True}

                else:

                    params = dict(step.parameters)

                    params = self._inject_context_params(
                        step.tool_name,
                        params,
                        context
                    )

                    result = self.tool_manager.execute_tool(
                        step.tool_name,
                        **params
                    )

                self._store_result(
                    step.tool_name,
                    result,
                    context
                )

                elapsed = (
                    datetime.now() - step_start
                ).total_seconds()

                # Check tool failure
                if isinstance(result, dict) and not result.get("success", True):
                    error_msg = result.get("error", "Unknown error")
                    self._log(
                        f"Step {step.step_id} FAIL | "
                        f"{step.tool_name} | {elapsed:.2f}s | {error_msg}"
                    )
                    # If web_search fails mid-research, return partial results
                    if step.tool_name == "web_search":
                        return (
                            f"I couldn't find information on that topic: {error_msg}"
                        )
                    return (
                        f"I had trouble with step '{step.description}': {error_msg}"
                    )

                self._log(
                    f"Step {step.step_id} OK | "
                    f"{step.tool_name} | {elapsed:.2f}s"
                )

            except Exception as e:

                elapsed = (
                    datetime.now() - step_start
                ).total_seconds()

                self._log(
                    f"Step {step.step_id} FAIL | "
                    f"{step.tool_name} | {elapsed:.2f}s | {e}"
                )

                return (
                    f"I ran into an error while trying to {step.description}: {e}"
                )

        total_time = (
            datetime.now() - start_time
        ).total_seconds()

        self._log(f"Plan complete | {total_time:.2f}s")

        return self._build_final_response(
            goal,
            context
        )

    def _inject_context_params(
        self,
        tool_name,
        params,
        context
    ):

        if tool_name == "file_read":

            file_paths = context.get("file_paths")

            if file_paths and "file_path" not in params:

                params["file_path"] = file_paths[0]

        if tool_name == "file_search":

            if "root_path" not in params:

                params["root_path"] = "."

        if tool_name == "web_search":

            if "query" in params:
                context.set(
                    "_research_query",
                    params["query"]
                )

        if tool_name == "web_crawl":

            top_sources = context.get(
                "_top_sources"
            )

            if top_sources and "urls" not in params:

                params["urls"] = [
                    s.url for s in top_sources
                ]

        return params

    def _run_summarize(
        self,
        context
    ):

        content = context.get("file_content")

        if not content:

            content = context.get(
                "research_content"
            )

        if not content:

            memories = context.get("memories")

            if memories:
                content = "\n".join(memories)

        if not content:

            sources = context.get("sources")

            if sources:
                lines = []
                for s in sources:
                    title = s.get("title", "")
                    body = s.get("body", s.get("snippet", ""))
                    url = s.get("url", "")
                    lines.append(f"{title}\n{body}\n{url}")
                content = "\n\n".join(lines)

        if not content:

            return "No content found to summarize."

        prompt = f"""
            Summarize the following content concisely:

            {content}

            Provide a clear and informative summary.
            """

        return self.llm.generate(prompt)

    def _store_result(
        self,
        tool_name,
        result,
        context
    ):

        if tool_name == "web_search":

            if isinstance(result, dict):

                sources = result.get("results", [])

                context.set("sources", sources)

                ranked = self.source_ranker.rank(
                    sources
                )

                top = self.source_ranker.select_top(
                    ranked,
                    n=self.top_sources_count
                )

                context.set(
                    "_top_sources",
                    top
                )

                citations = []

                for s in top:

                    citations.append({
                        "title": s.title,
                        "url": s.url,
                        "source_type": s.source_type
                    })

                context.set(
                    "_citations",
                    citations
                )

            return

        if tool_name == "web_crawl":

            raw_pages = context.get(
                "_raw_pages",
                []
            )

            top_sources = context.get(
                "_top_sources",
                []
            )

            url_to_source = {
                s.url: s
                for s in top_sources
            }

            if isinstance(result, dict) and result.get("success"):

                pages = result.get("pages")

                if pages is not None:

                    for page in pages:

                        url = page.get("url", "")
                        matched = url_to_source.get(url)

                        raw_pages.append({
                            "url": url,
                            "title": page.get("title", ""),
                            "content": page.get("content", ""),
                            "source_type": (
                                matched.source_type
                                if matched
                                else ""
                            )
                        })

                else:

                    url = result.get("url", "")
                    matched = url_to_source.get(url)

                    raw_pages.append({
                        "url": url,
                        "title": result.get("title", ""),
                        "content": result.get("content", ""),
                        "source_type": (
                            matched.source_type
                            if matched
                            else ""
                        )
                    })

            context.set("_raw_pages", raw_pages)

            return

        if tool_name == "content_process":

            raw_pages = context.get(
                "_raw_pages",
                []
            )

            processed = (
                self.content_processor.process(
                    raw_pages
                )
            )

            context.set(
                "research_content",
                processed
            )

            return

        if tool_name == "generate_report":

            query = context.get("_research_query", "")
            content = context.get(
                "research_content",
                ""
            )
            summary = context.get(
                "summary",
                ""
            )
            citations = context.get(
                "_citations",
                []
            )

            report = (
                self.report_generator.generate(
                    query,
                    content,
                    summary,
                    citations
                )
            )

            context.set("report", report)

            return

        if tool_name == "summarize":

            context.set(
                "summary",
                result if isinstance(result, str) else str(result)
            )

            return

        if not isinstance(result, dict):
            return

        if tool_name == "file_search":

            context.set(
                "file_paths",
                result.get("file_paths", [])
            )

        elif tool_name == "file_read":

            if result.get("success"):
                context.set(
                    "file_content",
                    result.get("content", "")
                )
            else:
                context.set(
                    "file_content",
                    result.get("error", "Failed to read file")
                )

        elif tool_name == "memory_search":

            context.set(
                "memories",
                result.get("memories", [])
            )

        elif tool_name == "calculator":

            if result.get("success"):
                context.set(
                    "calculation",
                    result.get("result", "")
                )
            else:
                context.set(
                    "calculation",
                    result.get("error", "Calculation failed")
                )

    def _build_final_response(
        self,
        goal,
        context
    ):

        if goal == "research_report":

            report = context.get("report")

            if report:

                return report

            summary = context.get("summary")

            if summary:
                return summary

            return "Research completed but no report was generated."

        if goal == "summarize":

            summary = context.get("summary")

            if not summary:

                file_content = context.get("file_content")

                if file_content:

                    prompt = f"""
                        Summarize the following content in a natural way:

                        {file_content}
                        """

                    return self.llm.generate(prompt)

            return summary

        if goal == "summarize_memories":

            summary = context.get("summary")

            if not summary:

                memories = context.get("memories")

                if memories:

                    memories_text = "\n".join(memories)

                    prompt = f"""
                        Summarize the following memories concisely:

                        {memories_text}
                        """

                    return self.llm.generate(prompt)

            return summary

        if goal == "find_and_read":

            content = context.get("file_content")

            if content:

                prompt = f"""
                    The user asked me to find and read a file.

                    Here is the file content:

                    {content}

                    Present this to the user in a clear, natural way.
                    """

                return self.llm.generate(prompt)

            return "No content was found."

        parts = []

        file_content = context.get("file_content")

        if file_content:
            parts.append(file_content)

        calculation = context.get("calculation")

        if calculation:
            parts.append(f"Result: {calculation}")

        if parts:
            return "\n\n".join(parts)

        return "I completed the task but found no content to return."

    def _log(
        self,
        message
    ):

        timestamp = datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S"
        )

        try:

            with open(
                self.log_path,
                "a",
                encoding="utf-8"
            ) as f:

                f.write(
                    f"[{timestamp}] {message}\n"
                )

        except Exception as e:
            logger.debug("Failed to write execution log: %s", e)
