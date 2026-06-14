import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from planner.plan import Plan
from planner.plan_step import PlanStep
from planner.plan_executor import PlanExecutor
from planner.execution_planner import ExecutionPlanner
from tools.tool_manager import ToolManager
from tools.web_search_tool import WebSearchTool
from tools.web_crawl_tool import WebCrawlTool

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


class MockLLM:

    def __init__(self):
        self.last_prompt = ""

    def generate(self, prompt):
        self.last_prompt = prompt
        return (
            "## Overview\nMock research report about the topic.\n"
            "## Key Features\n- Feature 1\n- Feature 2\n"
            "## Advantages\n- Advantage 1\n"
            "## Limitations\n- Limitation 1\n"
            "## Use Cases\n- Use case 1\n"
            "## Technical Details\n- Detail 1"
        )


class MockSearchProvider:

    def search(self, query, max_results=5):

        return [
            {
                "title": "Wikipedia Article",
                "url": "https://en.wikipedia.org/wiki/Pgvector",
                "snippet": "Wikipedia article about pgvector"
            },
            {
                "title": "GitHub Repo",
                "url": "https://github.com/pgvector/pgvector",
                "snippet": "Official GitHub repository"
            },
            {
                "title": "Random Blog",
                "url": "https://medium.com/pgvector-intro",
                "snippet": "Blog post about pgvector"
            },
        ]


print("=== Test: Research Workflow ===\n")

tm = ToolManager()

web_search = WebSearchTool(
    provider=MockSearchProvider()
)
tm.register_tool(web_search)

# For web_crawl, mock it at executor level
tm.register_tool(WebCrawlTool())

llm = MockLLM()
executor = PlanExecutor(tm, llm)

# Monkey-patch web_crawl to not use actual network
original_execute = tm.execute_tool


def mock_execute(tool_name, **kwargs):

    if tool_name == "web_crawl":

        urls = kwargs.get("urls")

        if isinstance(urls, list):

            pages = []

            for url in urls:

                pages.append({
                    "url": url,
                    "title": f"Page for {url}",
                    "content": (
                        "Mock crawled content about the topic. "
                        "It contains useful information for research."
                    ),
                    "success": True,
                    "error": ""
                })

            return {
                "success": True,
                "pages": pages,
                "total": len(urls),
                "crawled": len(pages)
            }

        url = kwargs.get("url", "")

        return {
            "success": True,
            "content": "Mock crawled content about the topic. "
                       "It contains useful information for research.",
            "url": url,
            "title": "Mock Page"
        }

    return original_execute(tool_name, **kwargs)


tm.execute_tool = mock_execute

# Test 1: Planner generates correct research plan
print("[Test 1: Planner generates research plan]")

planner = ExecutionPlanner()
plan = planner.create_plan("research pgvector")

check("plan is not None", plan is not None)
check("goal is research_report", plan.goal == "research_report")

if plan:
    tools = [s.tool_name for s in plan.steps]
    check(
        "5 steps in research plan",
        len(plan.steps) == 5
    )
    check(
        "starts with web_search",
        tools[0] == "web_search"
    )
    check(
        "has web_crawl",
        tools[1] == "web_crawl"
    )
    check(
        "has content_process",
        tools[2] == "content_process"
    )
    check(
        "has summarize",
        tools[3] == "summarize"
    )
    check(
        "ends with generate_report",
        tools[4] == "generate_report"
    )

# Test 2: Executor runs research plan
print("\n[Test 2: Executor runs research plan]")

if plan:
    result = executor.execute_plan(plan)

    check("executor returns result", result is not None)
    check("result is a string", isinstance(result, str))
    check("result contains overview", "Overview" in result)
    check("result contains key features", "Key Features" in result)

# Test 3: Context passing works for research
print("\n[Test 3: Context passing in research]")

context_data = {}

original_store = executor._store_result


def tracking_store(tool_name, result, context):
    original_store(tool_name, result, context)
    if tool_name == "web_search":
        context_data["sources_captured"] = True
        context_data["num_sources"] = len(
            context.get("sources", [])
        )
        top = context.get("_top_sources", [])
        context_data["top_sources_count"] = len(top)
        if top:
            context_data["top1_type"] = top[0].source_type
        citations = context.get("_citations", [])
        context_data["citations_count"] = len(citations)
    elif tool_name == "web_crawl":
        raw = context.get("_raw_pages", [])
        context_data["pages_crawled"] = len(raw)
        if raw:
            context_data["has_source_type"] = bool(
                raw[0].get("source_type")
            )
    elif tool_name == "content_process":
        context_data["research_content_captured"] = (
            context.get("research_content", "") != ""
        )
        content = context.get("research_content", "")
        context_data["has_source_type_label"] = "github" in content
    elif tool_name == "generate_report":
        context_data["report_captured"] = (
            context.get("report", "") != ""
        )


executor._store_result = tracking_store

if plan:
    executor.execute_plan(plan)

    check(
        "sources were captured",
        context_data.get("sources_captured", False)
    )
    check(
        "3 sources found",
        context_data.get("num_sources", 0) == 3
    )
    check(
        "top sources were ranked",
        context_data.get("top_sources_count", 0) == 3
    )
    check(
        "top source is github (highest score)",
        context_data.get("top1_type", "") == "github"
    )
    check(
        "citations were collected",
        context_data.get("citations_count", 0) == 3
    )
    check(
        "pages were crawled (from multi-source)",
        context_data.get("pages_crawled", 0) == 3
    )
    check(
        "crawled pages have source_type",
        context_data.get("has_source_type", False)
    )
    check(
        "source type labels in content",
        context_data.get("has_source_type_label", False)
    )
    check(
        "research content was processed",
        context_data.get("research_content_captured", False)
    )
    check(
        "report was generated",
        context_data.get("report_captured", False)
    )

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
