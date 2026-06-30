import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()


class Settings:

    def __init__(self):
        # Database
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:1234@localhost:5432/AIKA DB"
        )

        # LLM
        self.chat_model: str = os.getenv("CHAT_MODEL", "qwen2.5:3b")
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        self.ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))

        # Memory retrieval
        self.memory_retrieval_limit: int = int(os.getenv("MEMORY_RETRIEVAL_LIMIT", "8"))
        self.memory_candidate_multiplier: int = int(os.getenv("MEMORY_CANDIDATE_MULTIPLIER", "3"))
        self.memory_min_score: float = float(os.getenv("MEMORY_MIN_SCORE", "0.3"))
        self.memory_recency_half_life_hours: int = int(os.getenv("MEMORY_RECENCY_HALF_LIFE", "720"))
        self.memory_sim_weight: float = float(os.getenv("MEMORY_SIM_WEIGHT", "0.50"))
        self.memory_importance_weight: float = float(os.getenv("MEMORY_IMPORTANCE_WEIGHT", "0.20"))
        self.memory_profile_weight: float = float(os.getenv("MEMORY_PROFILE_WEIGHT", "0.10"))
        self.memory_access_weight: float = float(os.getenv("MEMORY_ACCESS_WEIGHT", "0.05"))
        self.memory_recency_weight: float = float(os.getenv("MEMORY_RECENCY_WEIGHT", "0.15"))
        self.memory_category_boost_project: float = float(os.getenv("MEMORY_BOOST_PROJECT", "0.3"))
        self.memory_category_boost_goal: float = float(os.getenv("MEMORY_BOOST_GOAL", "0.2"))
        self.memory_category_boost_skill: float = float(os.getenv("MEMORY_BOOST_SKILL", "0.1"))
        self.memory_max_per_category: int = int(os.getenv("MEMORY_MAX_PER_CATEGORY", "2"))
        self.memory_validator_min_score: float = float(os.getenv("MEMORY_VALIDATOR_MIN_SCORE", "0.92"))

        # Context
        self.max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "2000"))
        self.max_profile_per_category: int = int(os.getenv("MAX_PROFILE_PER_CATEGORY", "2"))
        self.recent_conversations_count: int = int(os.getenv("RECENT_CONVERSATIONS_COUNT", "10"))

        # Conversation
        self.conversation_max_count: int = int(os.getenv("CONVERSATION_MAX_COUNT", "100"))

        # Tools / Web
        self.web_search_max_results: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))

        # Planner & Research
        self.plan_web_search_max_results: int = int(os.getenv("PLAN_WEB_SEARCH_MAX_RESULTS", "5"))
        self.plan_top_sources_count: int = int(os.getenv("PLAN_TOP_SOURCES_COUNT", "3"))
        self.crawl_content_max_chars: int = int(os.getenv("CRAWL_CONTENT_MAX_CHARS", "2000"))

        # Input Validation
        self.max_input_length: int = int(os.getenv("MAX_INPUT_LENGTH", "10000"))
        self.max_calculation_length: int = int(os.getenv("MAX_CALCULATION_LENGTH", "200"))

        # Tools
        self.file_search_root_path: str = os.getenv("FILE_SEARCH_ROOT_PATH", ".")
        self.file_read_encoding: str = os.getenv("FILE_READ_ENCODING", "utf-8")

        # Paths
        self.execution_log_path: str = os.getenv("EXECUTION_LOG_PATH", "logs/execution.log")
        self.memory_data_path: str = os.getenv("MEMORY_DATA_PATH", "data/memories")
        self.conversation_data_path: str = os.getenv("CONVERSATION_DATA_PATH", "data/conversations")

        # OS / Shell
        self.shell_enabled: bool = os.getenv("SHELL_ENABLED", "true").lower() == "true"
        self.shell_timeout: int = int(os.getenv("SHELL_TIMEOUT", "30"))
        self.shell_blocked_keywords: list = os.getenv(
            "SHELL_BLOCKED_KEYWORDS",
            "rm -rf,format,del /,shutdown,rd /s,del /f,format c:,diskpart"
        ).split(",")
        self.app_launcher_enabled: bool = os.getenv("APP_LAUNCHER_ENABLED", "true").lower() == "true"
        self.app_launcher_uwp_enabled: bool = os.getenv("APP_LAUNCHER_UWP_ENABLED", "true").lower() == "true"

        # Persona
        self.persona_path: str = os.getenv("PERSONA_PATH", "src/config/persona.txt")

        # Logging
        self.log_level: str = os.getenv("LOG_LEVEL", "DEBUG")
        self.log_format: str = os.getenv("LOG_FORMAT", "[%(levelname)s] %(message)s")

    def load_persona(self):
        path = Path(self.persona_path)
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
        logger = logging.getLogger(__name__)
        logger.warning("Persona file not found: %s", path)
        return ""

    def reload(self):
        load_dotenv(override=True)
        self.__init__()


settings = Settings()
