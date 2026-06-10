import sys
from pathlib import Path

sys.path.append(
    str(
        Path(__file__).resolve().parent.parent / "src"
    )
)

from brain.brain import AikaBrain

brain = AikaBrain()

result = brain.tool_manager.execute_tool(
    "memory_search",
    query="AIKA"
)

print("\n=== MEMORY SEARCH TEST ===")
print(result)
print("=========================\n")