import time
import logging
from concurrent.futures import ThreadPoolExecutor

from config.settings import settings
from brain.decision_engine import DecisionEngine
from brain.intent_classifier import LLMIntentClassifier
from llm.ollama_client import OllamaClient

from handlers.memory_handler import MemoryHandler
from handlers.chat_handler import ChatHandler

from repositories.memory_repository import MemoryRepository
from repositories.conversation_repository import ConversationRepository

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

        # Chat Handler
        self.chat_handler = ChatHandler(
            self.conversation_repo,
            self.llm,
            self.memory_extractor,
            self.context_manager,
            tool_manager=self.tool_manager
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

    def process(self, user_message):

        t0 = time.time()

        # Decide action based on user message
        decision = self.decision_engine.decide(
            user_message
        )

        # Route to appropriate handler
        response = self.router.route(
            decision,
            user_message
        )

        total = time.time() - t0

        logger.debug("%s", "-" * 45)
        logger.debug("Decision: %s | Total: %.2fs", decision.value, total)

        # Background memory extraction (non-blocking)
        self._executor.submit(
            self.chat_handler.memory_extractor.extract_memory,
            user_message
        )
        logger.debug("Memory extraction -> background")

        return response