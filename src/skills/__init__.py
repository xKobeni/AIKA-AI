"""Local, declarative skill support for AIKA."""

from skills.manager import SkillManager
from skills.registry import SkillDefinition, SkillIssue, SkillRegistry

__all__ = [
    "SkillDefinition",
    "SkillIssue",
    "SkillManager",
    "SkillRegistry",
]
