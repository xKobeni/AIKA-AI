from brain.agent_context import AgentContext
from brain.common import FAIL_PHRASES

__all__ = ["AikaBrain", "AgentContext", "FAIL_PHRASES"]


def __getattr__(name):
    if name == "AikaBrain":
        from brain.brain import AikaBrain
        return AikaBrain
    raise AttributeError(f"module 'brain' has no attribute {name!r}")
