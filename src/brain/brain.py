import os
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Iterator

from config.settings import settings
from models.actions import Action
from brain.decision_engine import DecisionEngine
from brain.intent_classifier import LLMIntentClassifier
from brain.llm_tool_router import LLMToolRouter
from llm.ollama_client import OllamaClient

from handlers.memory_handler import MemoryHandler
from handlers.chat_handler import ChatHandler

from repositories.memory_repository import MemoryRepository
from repositories.conversation_repository import ConversationRepository
from repositories.session_repository import SessionRepository

from handlers.memory_extractor import MemoryExtractor
from handlers.tool_response_handler import ToolResponseHandler
from handlers.tool_handler import ToolHandler
from handlers.config_handler import ConfigHandler
from handlers.response_finalizer import ResponseFinalizer

from brain.context_manager import ContextManager
from brain.router import Router
from brain.agent_loop import AgentLoop
from brain.model_router import ModelRouter

from tools.tool_manager import ToolManager
from tools.default_tools import register_default_tools

from llm.embedding_service import EmbeddingService

from memory.memory_retrieval_service import (
    MemoryRetrievalService
)

from planner.execution_planner import ExecutionPlanner
from planner.plan_executor import PlanExecutor

from brain.orchestrator import Orchestrator

from agents.agent_registry import AgentRegistry, DEFAULT_AGENT_ID, PERSONAS_DIR


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
    format=settings.log_format
)
logger = logging.getLogger(__name__)


class AikaBrain:

    def __init__(self):

        # Agent Registry
        self.agent_registry = AgentRegistry()
        self.agent_registry.load_personas_from_dir()
        self.current_agent_id = DEFAULT_AGENT_ID

        # Core Services
        self.llm = OllamaClient()
        
        self.embedding_service = EmbeddingService()

        # Model Router (auto-switch between fast/smart models)
        self.model_router = ModelRouter()

        # Repositories
        self.memory_repo = MemoryRepository()
        self.conversation_repo = ConversationRepository()
        self.session_repo = SessionRepository()
        
        # Memory Extraction
        self.memory_extractor = MemoryExtractor(
            self.memory_repo,
            self.embedding_service
        )

        # Memory Intelligence V3
        self.memory_retrieval_service = (
            MemoryRetrievalService(
                self.memory_repo,
                self.embedding_service
            )
        )
        
        # Context Manager
        self.context_manager = ContextManager(
            self.memory_repo,
            self.conversation_repo,
            self.embedding_service,
            retrieval_service=self.memory_retrieval_service,
            session_repo=self.session_repo
        )
        
        # Tool Manager
        self.tool_manager = ToolManager()
        register_default_tools(
            self.tool_manager,
            self.memory_retrieval_service,
        )

        self.tool_response_handler = ToolResponseHandler(
            self.llm
        )
        
        self.tool_handler = ToolHandler(
            self.tool_manager,
            self.tool_response_handler,
            agent_registry=self.agent_registry
        )

        # Execution Planner
        self.planner = ExecutionPlanner()
        self.executor = PlanExecutor(
            self.tool_manager,
            self.llm
        )

        # Intent Classifier
        self.intent_classifier = LLMIntentClassifier(llm=self.llm)

        # Decision Engine (fallback)
        self.decision_engine = DecisionEngine(
            intent_classifier=self.intent_classifier
        )

        # LLM Tool Router (new)
        self.llm_tool_router = LLMToolRouter(self.tool_manager, llm=self.llm)

        # Handlers
        self.memory_handler = MemoryHandler(
            self.memory_repo,
            self.embedding_service,
            retrieval_service=self.memory_retrieval_service
        )

        # Session
        self.current_session = self.session_repo.create(
            agent_id=self.current_agent_id
        )

        self.response_finalizer = ResponseFinalizer(
            self.conversation_repo,
            embedding_service=self.embedding_service,
            session_repo=self.session_repo,
        )

        # Chat Handler
        self.chat_handler = ChatHandler(
            self.conversation_repo,
            self.llm,
            self.memory_extractor,
            self.context_manager,
            tool_manager=self.tool_manager,
            session_id=self.current_session.id,
            embedding_service=self.embedding_service,
            session_repo=self.session_repo,
            model_router=self.model_router,
            agent_registry=self.agent_registry,
            response_finalizer=self.response_finalizer,
        )

        # Config Handler
        self.config_handler = ConfigHandler(
            agent_registry=self.agent_registry,
            refresh_callback=self._refresh_from_settings,
        )

        # Router
        self.router = Router(
            self.memory_handler,
            self.chat_handler,
            tool_handler=self.tool_handler,
            conversation_repo=self.conversation_repo,
            planner=self.planner,
            executor=self.executor,
            intent_classifier=self.intent_classifier,
            config_handler=self.config_handler,
            llm=self.llm
        )

        # Agent Loop
        self.agent_loop = AgentLoop(
            self.decision_engine,
            self.router,
            self.llm,
            tool_manager=self.tool_manager,
            llm_tool_router=self.llm_tool_router,
            model_router=self.model_router,
            agent_registry=self.agent_registry
        )

        # Orchestrator
        self.orchestrator = Orchestrator(
            self.agent_registry,
            self.agent_loop,
            llm=self.llm,
            max_workers=4
        )

        # Wire orchestrator to router and agent loop
        self.router.orchestrator = self.orchestrator
        self.agent_loop._orchestrator = self.orchestrator

        self._executor = ThreadPoolExecutor(
            max_workers=4,
            thread_name_prefix="aika"
        )
        self._closed = False

    def close(self, wait=True):
        if getattr(self, "_closed", False):
            return
        self._closed = True
        executor = getattr(self, "_executor", None)
        if executor is not None:
            executor.shutdown(wait=wait, cancel_futures=not wait)
        for service in (
            getattr(self, "embedding_service", None),
            getattr(self, "llm", None),
        ):
            close = getattr(service, "close", None)
            if close:
                close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close(wait=True)

    def _refresh_from_settings(self, changed_keys=None):
        """Refresh existing components after runtime configuration changes."""
        refreshables = (
            self.llm,
            self.embedding_service,
            self.model_router,
            self.conversation_repo,
            self.context_manager,
            self.memory_handler,
            self.memory_extractor,
            self.chat_handler,
            self.llm_tool_router,
            self.intent_classifier,
            self.planner,
            self.executor,
            self.tool_handler,
            getattr(self, "agent_loop", None),
        )
        for component in refreshables:
            refresh = getattr(component, "refresh_from_settings", None)
            if refresh:
                refresh()

        for tool in self.tool_manager.tools.values():
            refresh = getattr(tool, "refresh_from_settings", None)
            if refresh:
                refresh()

        level = getattr(logging, settings.log_level.upper(), logging.DEBUG)
        logging.getLogger().setLevel(level)
        logger.info(
            "Refreshed runtime settings%s",
            f" for {sorted(changed_keys)}" if changed_keys else "",
        )

    def _schedule_memory_extraction(
        self,
        user_message,
        source_conversation_id
    ):
        if source_conversation_id is None:
            return
        if getattr(self, "_closed", False):
            logger.warning("Memory extraction skipped because AIKA is closed")
            return

        self._executor.submit(
            self.memory_extractor.extract_memory,
            user_message,
            source_conversation_id=source_conversation_id,
            agent_id=self.current_agent_id
        )
        logger.debug("Memory extraction -> background")

    def _complete_response(self, user_message, metadata=None, source_id=None):
        conversation_id = (
            metadata.user_conversation_id
            if metadata is not None
            else source_id
        )
        self._schedule_memory_extraction(user_message, conversation_id)

    def _finalize_agent_response(
        self, response, user_conversation, model_used, elapsed_seconds=None
    ):
        finalizer = getattr(self, "response_finalizer", None)
        if finalizer is None:
            finalizer = ResponseFinalizer(
                self.conversation_repo,
                embedding_service=self.embedding_service,
                session_repo=self.session_repo,
            )
            self.response_finalizer = finalizer
        metrics = {}
        llm = getattr(self, "llm", None)
        get_metrics = getattr(llm, "get_last_metrics", None)
        if callable(get_metrics):
            metrics = get_metrics() or {}
        if not isinstance(metrics, dict):
            metrics = {}
        response_tokens = metrics.get(
            "response_tokens", max(1, len(response) // 4) if response else 0
        )
        response_time_ms = metrics.get("response_time_ms")
        if response_time_ms is None and elapsed_seconds is not None:
            response_time_ms = int(elapsed_seconds * 1000)

        return finalizer.finalize(
            response,
            user_conversation_id=user_conversation.id,
            session_id=self.current_session.id,
            agent_id=self.current_agent_id,
            model_used=model_used,
            response_time_ms=response_time_ms,
            prompt_tokens=metrics.get("prompt_tokens"),
            response_tokens=response_tokens,
        )

    def _generate_session_summary(self, session_id):
        conversations = self.conversation_repo.get_by_session(
            session_id, limit=50
        )
        if not conversations:
            return
        transcript = "\n".join(
            f"{c.role}: {c.content}" for c in conversations
        )
        prompt = (
            f"Summarize this conversation in 2-3 sentences:\n\n"
            f"{transcript}\n\nSummary:"
        )
        summary = self.llm.generate(prompt)
        self.session_repo.update_summary(session_id, summary)

    def _handle_new_session(self):
        old_session_id = self.current_session.id
        self._executor.submit(
            self._generate_session_summary, old_session_id
        )
        self.current_session = self.session_repo.create(
            agent_id=self.current_agent_id
        )
        self.chat_handler.session_id = self.current_session.id
        return "New conversation started."

    def _resolve_session_id(self, partial):
        matches = self.session_repo.find_by_partial_id(partial)
        if len(matches) == 0:
            return None, f"No session matches '{partial}'."
        if len(matches) > 1:
            ids = ", ".join(s.id for s in matches)
            return None, f"Multiple sessions match '{partial}': {ids}"
        return matches[0], None

    def _handle_list_sessions(self):
        sessions = self.session_repo.get_all_sessions()
        if not sessions:
            return "No sessions found."
        lines = ["**Sessions:**"]
        for s in sessions:
            marker = " *" if s.id == self.current_session.id else "  "
            started = s.started_at.strftime("%Y-%m-%d %H:%M")
            summary = (
                (s.summary[:60] + "...")
                if s.summary and len(s.summary) > 60
                else (s.summary or "No summary yet")
            )
            lines.append(
                f"{marker} `{s.id}`  {started}  "
                f"{s.message_count} msgs  _{summary}_"
            )
        return "\n".join(lines)

    def _handle_resume_session(self, user_message):
        partial = user_message[len("resume "):].strip()
        session, err = self._resolve_session_id(partial)
        if err:
            return err
        self.current_session = session
        self.chat_handler.session_id = session.id
        summary = session.summary or "No summary available for this session."
        return (
            f"Resumed session `{session.id}`.\n"
            f"**Session summary:** {summary}"
        )

    def _handle_delete_session(self, user_message):
        partial = user_message[len("delete session "):].strip()
        session, err = self._resolve_session_id(partial)
        if err:
            return err
        was_current = session.id == self.current_session.id
        self.session_repo.delete(session.id)
        if was_current:
            self.current_session = self.session_repo.create(
                agent_id=self.current_agent_id
            )
            self.chat_handler.session_id = self.current_session.id
            return (
                f"Deleted current session `{session.id}`. "
                f"New session `{self.current_session.id}` started."
            )
        return f"Deleted session `{session.id}`."

    def _handle_list_agents(self):
        agents = self.agent_registry.get_all()
        if not agents:
            return "No agents registered."
        lines = ["**Agents:**"]
        for a in agents:
            marker = " *" if a.id == self.current_agent_id else "  "
            status = "active" if a.is_active else "inactive"
            model_str = f"model={a.model}" if a.model else "model=default"
            tools_str = "tools=all" if not a.allowed_tools else f"tools={len(a.allowed_tools)}"
            lines.append(
                f"{marker} `{a.id}` — {a.name} [{status}] {model_str}, {tools_str}"
            )
        lines.append("\nUse `use <agent_id>` to switch agents.")
        return "\n".join(lines)

    def _handle_use_agent(self, user_message):
        agent_id = user_message[len("use "):].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            available = ", ".join(a.id for a in self.agent_registry.get_all())
            return f"Agent '{agent_id}' not found. Available: {available}"
        if not profile.is_active:
            return f"Agent '{agent_id}' is inactive."
        self.current_agent_id = agent_id
        self.current_session = self.session_repo.create(agent_id=agent_id)
        self.chat_handler.session_id = self.current_session.id
        return f"Switched to agent `{agent_id}` ({profile.name}). New session `{self.current_session.id}` started."

    def _handle_create_agent(self, user_message):
        parts = user_message[len("create agent "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: create agent <id> <name> [model=<model>]"
        agent_id = parts[0]
        rest = parts[1]
        model = None
        if " model=" in rest.lower():
            idx = rest.lower().index(" model=")
            name = rest[:idx].strip()
            model_str = rest[idx + 7:].strip()
            model = model_str if model_str else None
        else:
            name = rest
        if model:
            available = self.llm.list_models()
            if available and model not in available:
                return f"Model '{model}' not found locally. Available: {', '.join(available)}"
        profile = self.agent_registry.create_agent(agent_id, name, model=model)
        if not profile:
            return f"Agent '{agent_id}' already exists."
        model_msg = f" model={model}" if model else ""
        return f"Created agent `{agent_id}` ({name}{model_msg}). Use `use {agent_id}` to switch."

    def _handle_set_agent_tools(self, user_message):
        parts = user_message[len("set agent tools "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: set agent tools <agent_id> <tool1,tool2,...> or 'all'"
        agent_id = parts[0]
        tools_str = parts[1].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            return f"Agent '{agent_id}' not found."
        if tools_str.lower() == "all":
            profile.allowed_tools = None
        else:
            tool_names = [t.strip() for t in tools_str.split(",")]
            invalid = [t for t in tool_names if t not in self.tool_manager.tools]
            if invalid:
                available = ", ".join(sorted(self.tool_manager.tools.keys()))
                return f"Unknown tools: {', '.join(invalid)}. Available: {available}"
            profile.allowed_tools = tool_names
        self.agent_registry.register(profile)
        count = len(profile.allowed_tools) if profile.allowed_tools else "all"
        return f"Agent '{agent_id}' tools updated: {count} tools."

    def _handle_show_agent_tools(self, user_message):
        agent_id = user_message[len("show agent tools "):].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            return f"Agent '{agent_id}' not found."
        if not profile.allowed_tools:
            return f"Agent '{agent_id}' has access to ALL tools."
        return (
            f"Agent '{agent_id}' allowed tools:\n"
            + "\n".join(f"  - {t}" for t in profile.allowed_tools)
        )

    def _handle_set_agent_model(self, user_message):
        parts = user_message[len("set agent model "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: set agent model <agent_id> <model_name>"
        agent_id = parts[0]
        model_name = parts[1].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            return f"Agent '{agent_id}' not found."
        available = self.llm.list_models()
        if available and model_name not in available:
            return f"Model '{model_name}' not found locally. Available: {', '.join(available)}"
        self.agent_registry.set_model(agent_id, model_name)
        return f"Agent '{agent_id}' model set to `{model_name}`."

    def _handle_show_agent_model(self, user_message):
        agent_id = user_message[len("show agent model "):].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            return f"Agent '{agent_id}' not found."
        model = profile.model or f"(default: {settings.chat_model})"
        return f"Agent '{agent_id}' model: {model}"

    def _handle_set_agent_persona(self, user_message):
        parts = user_message[len("set agent persona "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: set agent persona <agent_id> <persona_text>"
        agent_id = parts[0]
        persona_text = parts[1].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            return f"Agent '{agent_id}' not found."
        os.makedirs(PERSONAS_DIR, exist_ok=True)
        persona_path = os.path.join(PERSONAS_DIR, f"{agent_id}.txt")
        try:
            with open(persona_path, "w", encoding="utf-8") as f:
                f.write(persona_text)
        except Exception as e:
            return f"Failed to write persona file: {e}"
        self.agent_registry.set_persona(agent_id, persona_path)
        return f"Agent '{agent_id}' persona updated. File: {persona_path}"

    def _handle_show_agent_persona(self, user_message):
        agent_id = user_message[len("show agent persona "):].strip()
        profile = self.agent_registry.get(agent_id)
        if not profile:
            return f"Agent '{agent_id}' not found."
        if not profile.persona_path:
            return f"Agent '{agent_id}' has no persona file set."
        if not os.path.exists(profile.persona_path):
            return f"Agent '{agent_id}' persona file not found: {profile.persona_path}"
        try:
            with open(profile.persona_path, "r", encoding="utf-8") as f:
                content = f.read()
            return (
                f"Agent '{agent_id}' persona ({profile.persona_path}):\n"
                f"---\n{content}\n---"
            )
        except Exception as e:
            return f"Failed to read persona file: {e}"

    def _handle_list_models(self):
        models = self.llm.list_models()
        if not models:
            return "No Ollama models found locally."
        return "Available Ollama models:\n" + "\n".join(f"  - {m}" for m in models)

    def _handle_delegate(self, user_message):
        parts = user_message[len("delegate "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: delegate <agent_id> <task>"
        target_agent = parts[0]
        task = parts[1]
        result = self.orchestrator.delegate(self.current_agent_id, task, target_agent)
        return result

    def _handle_chain(self, user_message):
        parts = user_message[len("chain "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: chain <agent1>,<agent2> ... <task>"
        agent_list_str = parts[0]
        task = parts[1]
        agent_ids = [a.strip() for a in agent_list_str.split(",")]
        result = self.orchestrator.run_chain(agent_ids, task)
        return result

    def _handle_team(self, user_message):
        parts = user_message[len("team "):].strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: team <agent1>,<agent2> ... <task>"
        agent_list_str = parts[0]
        task = parts[1]
        agent_ids = [a.strip() for a in agent_list_str.split(",")]
        result = self.orchestrator.run_team(agent_ids, task)
        return result

    def _handle_agents_status(self):
        teams = self.orchestrator.get_team_status()
        if not teams:
            return "No active teams."
        lines = ["**Agent Teams:**"]
        for team_id, info in teams.items():
            lines.append(f"  `{team_id}`: {info['status']} | {info['turns']} turns | agents: {', '.join(info['agents'])}")
        return "\n".join(lines)

    def process(self, user_message):

        t0 = time.time()

        cmd = user_message.lower().strip()

        if cmd == "list agents":
            response = self._handle_list_agents()
            logger.debug("Route: LIST_AGENTS (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("use "):
            response = self._handle_use_agent(cmd)
            logger.debug("Route: USE_AGENT (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("create agent "):
            response = self._handle_create_agent(cmd)
            logger.debug("Route: CREATE_AGENT (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("set agent tools "):
            response = self._handle_set_agent_tools(cmd)
            logger.debug("Route: SET_AGENT_TOOLS (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("show agent tools "):
            response = self._handle_show_agent_tools(cmd)
            logger.debug("Route: SHOW_AGENT_TOOLS (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("set agent model "):
            response = self._handle_set_agent_model(cmd)
            logger.debug("Route: SET_AGENT_MODEL (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("show agent model "):
            response = self._handle_show_agent_model(cmd)
            logger.debug("Route: SHOW_AGENT_MODEL (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("set agent persona "):
            response = self._handle_set_agent_persona(cmd)
            logger.debug("Route: SET_AGENT_PERSONA (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("show agent persona "):
            response = self._handle_show_agent_persona(cmd)
            logger.debug("Route: SHOW_AGENT_PERSONA (%.2fs)", time.time() - t0)
            return response

        if cmd == "list models":
            response = self._handle_list_models()
            logger.debug("Route: LIST_MODELS (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("delegate "):
            response = self._handle_delegate(cmd)
            logger.debug("Route: DELEGATE (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("chain "):
            response = self._handle_chain(cmd)
            logger.debug("Route: CHAIN (%.2fs)", time.time() - t0)
            return response

        if cmd.startswith("team "):
            response = self._handle_team(cmd)
            logger.debug("Route: TEAM (%.2fs)", time.time() - t0)
            return response

        if cmd == "agents status":
            response = self._handle_agents_status()
            logger.debug("Route: AGENTS_STATUS (%.2fs)", time.time() - t0)
            return response

        decision = self.decision_engine.decide(user_message)
        source_conversation_id = None
        response_metadata = None

        if decision == Action.NEW_SESSION:
            response = self._handle_new_session()
            logger.debug("Route: NEW_SESSION (%.2fs)", time.time() - t0)
        elif decision == Action.LIST_SESSIONS:
            response = self._handle_list_sessions()
            logger.debug("Route: LIST_SESSIONS (%.2fs)", time.time() - t0)
        elif decision == Action.RESUME_SESSION:
            response = self._handle_resume_session(user_message)
            logger.debug("Route: RESUME_SESSION (%.2fs)", time.time() - t0)
        elif decision == Action.DELETE_SESSION:
            response = self._handle_delete_session(user_message)
            logger.debug("Route: DELETE_SESSION (%.2fs)", time.time() - t0)
        elif decision == Action.CONFIGURE:
            response = self.config_handler.handle(user_message)
            logger.debug("Route: CONFIGURE (%.2fs)", time.time() - t0)
        elif decision == Action.CHAT:
            response = self.chat_handler.chat(
                user_message,
                intent=decision.value,
                agent_id=self.current_agent_id
            )
            source_conversation_id = self.chat_handler._last_user_conv_id
            response_metadata = getattr(
                self.chat_handler, "last_response_metadata", None
            )
            logger.debug("Route: CHAT (%.2fs)", time.time() - t0)
        else:
            user_embedding = None
            try:
                user_embedding = self.embedding_service.generate_embedding(user_message)
            except Exception as e:
                logger.warning("Failed to generate user embedding: %s", e)

            user_conv = self.conversation_repo.create(
                role="user",
                content=user_message,
                session_id=self.current_session.id,
                embedding=user_embedding,
                agent_id=self.current_agent_id,
            )
            source_conversation_id = user_conv.id

            agent_started = time.time()
            response = self.agent_loop.run(
                user_message,
                agent_id=self.current_agent_id
            )
            agent_elapsed = time.time() - agent_started

            response_metadata = self._finalize_agent_response(
                response,
                user_conv,
                self.agent_loop.last_model_used,
                elapsed_seconds=agent_elapsed,
            )

            logger.debug("Route: AGENT_LOOP (%.2fs)", time.time() - t0)

        total = time.time() - t0

        logger.debug("%s", "-" * 45)
        logger.debug("Decision: %s | Total: %.2fs", decision.value, total)

        self._complete_response(
            user_message,
            metadata=response_metadata,
            source_id=source_conversation_id,
        )

        return response

    def process_stream(self, user_message) -> Iterator[str]:

        t0 = time.time()

        cmd = user_message.lower().strip()

        if cmd == "list agents":
            yield self._handle_list_agents()
            return

        if cmd.startswith("use "):
            yield self._handle_use_agent(cmd)
            return

        if cmd.startswith("create agent "):
            yield self._handle_create_agent(cmd)
            return

        if cmd.startswith("set agent tools "):
            yield self._handle_set_agent_tools(cmd)
            return

        if cmd.startswith("show agent tools "):
            yield self._handle_show_agent_tools(cmd)
            return

        if cmd.startswith("set agent model "):
            yield self._handle_set_agent_model(cmd)
            return

        if cmd.startswith("show agent model "):
            yield self._handle_show_agent_model(cmd)
            return

        if cmd.startswith("set agent persona "):
            yield self._handle_set_agent_persona(cmd)
            return

        if cmd.startswith("show agent persona "):
            yield self._handle_show_agent_persona(cmd)
            return

        if cmd == "list models":
            yield self._handle_list_models()
            return

        if cmd.startswith("delegate "):
            yield self._handle_delegate(cmd)
            return

        if cmd.startswith("chain "):
            yield self._handle_chain(cmd)
            return

        if cmd.startswith("team "):
            yield self._handle_team(cmd)
            return

        if cmd == "agents status":
            yield self._handle_agents_status()
            return

        decision = self.decision_engine.decide(user_message)

        if decision == Action.NEW_SESSION:
            yield self._handle_new_session()
            logger.debug("Route: NEW_SESSION (%.2fs)", time.time() - t0)
            return
        elif decision == Action.LIST_SESSIONS:
            yield self._handle_list_sessions()
            logger.debug("Route: LIST_SESSIONS (%.2fs)", time.time() - t0)
            return
        elif decision == Action.RESUME_SESSION:
            yield self._handle_resume_session(user_message)
            logger.debug("Route: RESUME_SESSION (%.2fs)", time.time() - t0)
            return
        elif decision == Action.DELETE_SESSION:
            yield self._handle_delete_session(user_message)
            logger.debug("Route: DELETE_SESSION (%.2fs)", time.time() - t0)
            return
        elif decision == Action.CONFIGURE:
            yield self.config_handler.handle(user_message)
            logger.debug("Route: CONFIGURE (%.2fs)", time.time() - t0)
            return
        elif decision == Action.CHAT:
            yield from self.chat_handler.chat_stream(
                user_message,
                intent=decision.value,
                agent_id=self.current_agent_id
            )
            self._complete_response(
                user_message,
                metadata=getattr(
                    self.chat_handler, "last_response_metadata", None
                ),
                source_id=self.chat_handler._last_user_conv_id,
            )
            logger.debug("Route: CHAT_STREAM (%.2fs)", time.time() - t0)
            return

        user_embedding = None
        try:
            user_embedding = self.embedding_service.generate_embedding(user_message)
        except Exception as e:
            logger.warning("Failed to generate user embedding: %s", e)

        user_conv = self.conversation_repo.create(
            role="user",
            content=user_message,
            session_id=self.current_session.id,
            embedding=user_embedding,
            agent_id=self.current_agent_id,
        )

        response_chunks = []
        agent_started = time.time()
        for chunk in self.agent_loop.run_stream(
            user_message,
            agent_id=self.current_agent_id
        ):
            response_chunks.append(chunk)
            yield chunk

        response = "".join(response_chunks)
        agent_elapsed = time.time() - agent_started

        response_metadata = self._finalize_agent_response(
            response,
            user_conv,
            self.agent_loop.last_model_used,
            elapsed_seconds=agent_elapsed,
        )

        logger.debug("Route: AGENT_LOOP (%.2fs)", time.time() - t0)

        total = time.time() - t0
        logger.debug("%s", "-" * 45)
        logger.debug("Decision: %s | Total: %.2fs", decision.value, total)

        self._complete_response(
            user_message,
            metadata=response_metadata,
        )
