import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from research.report_generator import ReportGenerator

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
            "## Overview\npgvector is a PostgreSQL extension "
            "for vector similarity search.\n\n"
            "## Key Features\n- Cosine similarity\n- "
            "L2 distance\n- Inner product\n\n"
            "## Advantages\n- Native PostgreSQL integration\n"
            "- ACID compliant\n\n"
            "## Limitations\n- Requires pgvector extension\n"
            "- Index build time\n\n"
            "## Use Cases\n- Semantic search\n- "
            "RAG applications\n\n"
            "## Technical Details\n- Uses IVFFlat indexes\n"
            "- Supports HNSW in newer versions"
        )


print("=== Test: ReportGenerator ===\n")

llm = MockLLM()
gen = ReportGenerator(llm)

# Test 1: Generate report
print("[Test 1: Generate report]")

report = gen.generate(
    query="pgvector",
    content="pgvector is a PostgreSQL extension for vector similarity search. "
            "It supports cosine similarity, L2 distance, and inner product. "
            "It uses IVFFlat indexes.",
    summary="pgvector enables vector search in PostgreSQL."
)

check("returns a string", isinstance(report, str))
check("report is non-empty", len(report) > 0)
check("contains Overview section", "Overview" in report)
check("contains Key Features section", "Key Features" in report)
check("contains Advantages section", "Advantages" in report)
check("contains Limitations section", "Limitations" in report)
check("contains Use Cases section", "Use Cases" in report)
check("contains Technical Details section", "Technical Details" in report)

# Test 2: LLM prompt contains the research topic
print("\n[Test 2: LLM prompt contains query]")

check(
    "prompt contains research topic",
    "pgvector" in llm.last_prompt
)
check(
    "prompt contains research content",
    "PostgreSQL extension" in llm.last_prompt
)

# Test 3: Generate report without summary
print("\n[Test 3: Report without summary]")

llm.last_prompt = ""
report = gen.generate(
    query="LangGraph",
    content="LangGraph is a framework for building "
            "stateful, multi-agent applications.",
    summary=""
)

check("report is generated without summary", len(report) > 0)
check("prompt contains topic without summary", "LangGraph" in llm.last_prompt)

# Test 4: Empty content
print("\n[Test 4: Empty content]")

llm.last_prompt = ""
report = gen.generate(
    query="test",
    content="",
    summary=""
)

check("handles empty content gracefully", report is not None)

print(f"\n=== Results: {passed} passed, {failed} failed ===\n")
