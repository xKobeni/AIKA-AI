from brain.decision_engine import DecisionEngine
from llm.ollama_client import OllamaClient

from handlers.memory_handler import MemoryHandler
from handlers.chat_handler import ChatHandler
from handlers.tool_handler import ToolHandler

from repositories.memory_repository import MemoryRepository
from repositories.conversation_repository import ConversationRepository

from handlers.memory_extractor import MemoryExtractor
from handlers.memory_validator import MemoryValidator
from handlers.tool_response_handler import ToolResponseHandler
from handlers.tool_handler import ToolHandler

from brain.context_manager import ContextManager
from brain.router import Router

from tools.tool_manager import ToolManager
from tools.calculator_tool import CalculatorTool
from tools.memory_search_tool import MemorySearchTool

from llm.embedding_service import EmbeddingService


class AikaBrain:

    def __init__(self):

        # Core Services
        self.llm = OllamaClient()
        
        self.embedding_service = EmbeddingService()

        # Repositories
        self.memory_repo = MemoryRepository()
        self.conversation_repo = ConversationRepository()
        
        # Memory Extraction and Validation
        self.memory_validator = MemoryValidator(
            self.llm,
            memory_repo=self.memory_repo,
            embedding_service=self.embedding_service
        )
        self.memory_extractor = MemoryExtractor(
            self.memory_repo,
            self.embedding_service,
            self.llm,
            self.memory_validator
        )
        
        # Context Manager
        self.context_manager = ContextManager(
            self.memory_repo,
            self.conversation_repo,
            self.embedding_service
        )
        
        # Tool Manager
        self.tool_manager = ToolManager()
        self.tool_manager.register_tool(
            CalculatorTool()
        )
        
        self.tool_response_handler = ToolResponseHandler(
            self.llm
        )
        
        self.tool_handler = ToolHandler(
            self.tool_manager,
            self.tool_response_handler
        )
        
        self.tool_manager.register_tool(
            MemorySearchTool(
                self.memory_repo,
                self.embedding_service
            )
        )

        # Decision Engine
        self.decision_engine = DecisionEngine()

        # Handlers
        self.memory_handler = MemoryHandler(
            self.memory_repo,
            self.embedding_service
        )

        # Chat Handler
        self.chat_handler = ChatHandler(
            self.conversation_repo,
            self.llm,
            self.memory_extractor,
            self.context_manager
        )

        # Router
        self.router = Router(
            self.memory_handler,
            self.chat_handler,
            tool_handler=self.tool_handler
        )
        

    def process(self, user_message):
        # # Save user message
        # self.memory.save_conversation(
        #     "user",
        #     user_message
        # )

        # Decide action based on user message
        decision = self.decision_engine.decide(
            user_message
        )
        
        # Debug: Print decision
        #print(f"[Decision Engine] -> {decision.value}")   
        
        # call appropriate handler based on decision
        response = self.router.route(
            decision,
            user_message
        )
        
        return response