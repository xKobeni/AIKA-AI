import time
import logging
from concurrent.futures import ThreadPoolExecutor

from config.settings import settings
from models.actions import Action
from brain.decision_engine import DecisionEngine
from brain.intent_classifier import LLMIntentClassifier
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

from brain.context_manager import ContextManager
from brain.router import Router

from tools.tool_manager import ToolManager
from tools.calculator_tool import CalculatorTool
from tools.memory_search_tool import MemorySearchTool
from tools.file_search_tool import FileSearchTool
from tools.file_read_tool import FileReadTool
from tools.web_search_tool import WebSearchTool
from tools.web_crawl_tool import WebCrawlTool
from tools.shell_tool import ShellTool
from tools.app_launcher_tool import AppLauncherTool
from tools.folder_tool import FolderTool
from tools.system_info_tool import SystemInfoTool

from llm.embedding_service import EmbeddingService

from memory.memory_retrieval_service import (
    MemoryRetrievalService
)

from planner.execution_planner import ExecutionPlanner
from planner.plan_executor import PlanExecutor


logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.DEBUG),
    format=settings.log_format
)
logger = logging.getLogger(__name__)


class AikaBrain:

    def __init__(self):

        # Core Services
        self.llm = OllamaClient()
        
        self.embedding_service = EmbeddingService()

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
            retrieval_service=self.memory_retrieval_service
        )
        
        # Tool Manager
        self.tool_manager = ToolManager()
        self.tool_manager.register_tool(
            CalculatorTool()
        )
        self.tool_manager.register_tool(
            FileSearchTool()
        )
        self.tool_manager.register_tool(
            FileReadTool()
        )
        self.tool_manager.register_tool(
            WebSearchTool()
        )
        self.tool_manager.register_tool(
            WebCrawlTool()
        )

        self.tool_manager.register_tool(
            MemorySearchTool(
                self.memory_retrieval_service
            )
        )

        self.tool_manager.register_tool(
            ShellTool()
        )

        self.tool_manager.register_tool(
            AppLauncherTool()
        )

        self.tool_manager.register_tool(
            FolderTool()
        )

        self.tool_manager.register_tool(
            SystemInfoTool()
        )

        self.tool_response_handler = ToolResponseHandler(
            self.llm
        )
        
        self.tool_handler = ToolHandler(
            self.tool_manager,
            self.tool_response_handler
        )

        # Execution Planner
        self.planner = ExecutionPlanner()
        self.executor = PlanExecutor(
            self.tool_manager,
            self.llm
        )

        # Intent Classifier
        self.intent_classifier = LLMIntentClassifier()

        # Decision Engine
        self.decision_engine = DecisionEngine(
            intent_classifier=self.intent_classifier
        )

        # Handlers
        self.memory_handler = MemoryHandler(
            self.memory_repo,
            self.embedding_service,
            retrieval_service=self.memory_retrieval_service
        )

        # Session
        self.current_session = self.session_repo.create()

        # Chat Handler
        self.chat_handler = ChatHandler(
            self.conversation_repo,
            self.llm,
            self.memory_extractor,
            self.context_manager,
            tool_manager=self.tool_manager,
            session_id=self.current_session.id,
            embedding_service=self.embedding_service,
            session_repo=self.session_repo
        )

        # Config Handler
        self.config_handler = ConfigHandler()

        # Router
        self.router = Router(
            self.memory_handler,
            self.chat_handler,
            tool_handler=self.tool_handler,
            conversation_repo=self.conversation_repo,
            planner=self.planner,
            executor=self.executor,
            intent_classifier=self.intent_classifier,
            config_handler=self.config_handler
        )

        self._executor = ThreadPoolExecutor(
            max_workers=2,
            thread_name_prefix="aika"
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
        self.current_session = self.session_repo.create()
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
            self.current_session = self.session_repo.create()
            self.chat_handler.session_id = self.current_session.id
            return (
                f"Deleted current session `{session.id}`. "
                f"New session `{self.current_session.id}` started."
            )
        return f"Deleted session `{session.id}`."

    def process(self, user_message):

        t0 = time.time()

        # Decide action based on user message
        decision = self.decision_engine.decide(
            user_message
        )

        # Handle session commands directly (bypasses router)
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
        else:
            response = self.router.route(
                decision,
                user_message
            )

        total = time.time() - t0

        logger.debug("%s", "-" * 45)
        logger.debug("Decision: %s | Total: %.2fs", decision.value, total)

        # Background memory extraction (non-blocking)
        source_conv_id = getattr(self.chat_handler, '_last_user_conv_id', None)
        self._executor.submit(
            self.chat_handler.memory_extractor.extract_memory,
            user_message,
            source_conversation_id=source_conv_id
        )
        logger.debug("Memory extraction -> background")

        return response