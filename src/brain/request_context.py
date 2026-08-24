import logging
import os
from dataclasses import dataclass
from datetime import datetime

from config.settings import settings


logger = logging.getLogger(__name__)

AIKA_GROUNDING_RULES = """=== IDENTITY AND GROUNDING RULES ===
- You are an AI, not a human. Be warm, but do not claim real feelings, consciousness, friends, a personal life, or lived experiences.
- Use only supplied conversation history and memories for continuity. Do not claim a first interaction when history is present, and do not claim to remember information absent from context.
- Describe only capabilities listed for the current agent. Do not claim an action succeeded unless a successful tool result confirms it.
- Never fabricate facts, dates, sources, memories, experiences, or completed actions."""


@dataclass(frozen=True)
class RequestContext:
    """Shared, immutable context supplied to chat and agent/tool prompts."""

    user_message: str
    agent_id: str | None
    session_id: str | None
    persona: str
    current_time: str
    current_date: str
    memory_context: str
    conversation_context: str
    cross_session_context: str
    allowed_tools: tuple[str, ...]

    def prompt_sections(self, *, include_persona=True):
        sections = []
        if include_persona and self.persona.strip():
            sections.append(self.persona)
        sections.append(
            f"Current time: {self.current_time}\n"
            f"Current date: {self.current_date}"
        )
        sections.append(AIKA_GROUNDING_RULES)
        if self.allowed_tools:
            sections.append(
                "=== TOOLS AVAILABLE TO THE CURRENT AGENT ===\n"
                + ", ".join(self.allowed_tools)
            )
        if self.memory_context.strip():
            sections.append(
                "=== WHAT YOU KNOW ABOUT THE USER ===\n"
                + self.memory_context
            )
        if self.conversation_context.strip():
            sections.append(
                "=== RECENT CONVERSATION ===\n"
                + self.conversation_context
            )
        if self.cross_session_context.strip():
            sections.append(
                "=== RELEVANT PAST DISCUSSIONS ===\n"
                + self.cross_session_context
            )
        return sections


class RequestContextBuilder:
    def __init__(
        self,
        context_manager,
        *,
        agent_registry=None,
        tool_manager=None,
        clock=None,
        persona_loader=None,
    ):
        self.context_manager = context_manager
        self.agent_registry = agent_registry
        self.tool_manager = tool_manager
        self.clock = clock
        self.persona_loader = persona_loader

    def _load_persona(self, agent_id):
        if self.persona_loader is not None:
            return str(self.persona_loader(agent_id) or "").strip()
        if agent_id and self.agent_registry:
            profile = self.agent_registry.get(agent_id)
            persona_path = getattr(profile, "persona_path", None)
            if persona_path and os.path.exists(persona_path):
                try:
                    with open(persona_path, "r", encoding="utf-8") as file:
                        return file.read().strip()
                except Exception as exc:
                    logger.warning(
                        "Failed to load persona for agent %s: %s",
                        agent_id,
                        type(exc).__name__,
                    )
        return settings.load_persona()

    def _allowed_tools(self, agent_id):
        if self.tool_manager is None:
            return ()
        registered = set(self.tool_manager.tools.keys())
        profile = (
            self.agent_registry.get(agent_id)
            if agent_id and self.agent_registry
            else None
        )
        configured = getattr(profile, "allowed_tools", None)
        if configured:
            registered.intersection_update(configured)
        return tuple(sorted(registered))

    def build(
        self,
        user_message,
        *,
        session_id=None,
        agent_id=None,
        query_embedding=None,
    ):
        context = self.context_manager.build_context(
            user_message,
            session_id=session_id,
            agent_id=agent_id,
            query_embedding=query_embedding,
        )
        now = (
            self.clock()
            if self.clock is not None
            else datetime.now().astimezone()
        )
        return RequestContext(
            user_message=user_message,
            agent_id=agent_id,
            session_id=session_id,
            persona=self._load_persona(agent_id),
            current_time=now.strftime("%H:%M"),
            current_date=now.strftime("%A, %B %d, %Y"),
            memory_context=str(context.get("memory_context", "") or ""),
            conversation_context=str(
                context.get("conversation_context", "") or ""
            ),
            cross_session_context=str(
                context.get("cross_session_context", "") or ""
            ),
            allowed_tools=self._allowed_tools(agent_id),
        )
