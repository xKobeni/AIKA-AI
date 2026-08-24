import os
import logging
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

DEFAULT_LOG_FORMAT = "[%(levelname)s] %(message)s"


def _validate_log_format(value: str) -> str:
    try:
        logging.Formatter(value)
    except (TypeError, ValueError):
        logging.getLogger(__name__).warning(
            "Invalid LOG_FORMAT; using the default logging format."
        )
        return DEFAULT_LOG_FORMAT
    return value


class Settings:

    def __init__(self):
        # Database
        self.database_url: str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:1234@localhost:5432/AIKA DB"
        )

        # LLM
        self.chat_model: str = os.getenv("CHAT_MODEL", "qwen2.5:3b")
        self.fast_model: str = os.getenv("FAST_MODEL", "qwen2.5:3b")
        self.smart_model: str = os.getenv("SMART_MODEL", "llama3:8b")
        self.embedding_model: str = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")
        self.ollama_host: str = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        self.llm_timeout: int = int(os.getenv("LLM_TIMEOUT", "30"))
        self.model_router_long_message_words: int = int(os.getenv(
            "MODEL_ROUTER_LONG_MESSAGE_WORDS", "20"
        ))
        self.model_router_complex_question_words: int = int(os.getenv(
            "MODEL_ROUTER_COMPLEX_QUESTION_WORDS", "12"
        ))
        self.model_router_escalation_iteration: int = int(os.getenv(
            "MODEL_ROUTER_ESCALATION_ITERATION", "2"
        ))
        self.model_router_complex_keywords: list = [
            value.strip().lower() for value in os.getenv(
                "MODEL_ROUTER_COMPLEX_KEYWORDS",
                "analyze,research,compare,explain why,how does,write code,"
                "debug,refactor,summarize,plan,step by step,multi,review,"
                "inspect,investigate,evaluate,design,architect,optimize,improve"
            ).split(",") if value.strip()
        ]
        self.model_router_tool_heavy_prefixes: list = [
            value.strip().lower() for value in os.getenv(
                "MODEL_ROUTER_TOOL_HEAVY_PREFIXES",
                "find and,read and,search and,check and,list and,get and"
            ).split(",") if value.strip()
        ]

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
        self.memory_dedup_threshold: float = float(os.getenv("MEMORY_DEDUP_THRESHOLD", "0.92"))
        self.memory_extraction_max_per_message: int = int(os.getenv("MEMORY_EXTRACTION_MAX_PER_MESSAGE", "3"))

        # Context
        self.max_context_tokens: int = int(os.getenv("MAX_CONTEXT_TOKENS", "6000"))
        self.max_profile_per_category: int = int(os.getenv("MAX_PROFILE_PER_CATEGORY", "2"))
        self.recent_conversations_count: int = int(os.getenv("RECENT_CONVERSATIONS_COUNT", "10"))
        self.context_session_summaries_count: int = int(os.getenv("CONTEXT_SESSION_SUMMARIES_COUNT", "5"))
        self.context_cross_session_conversations: int = int(os.getenv("CONTEXT_CROSS_SESSION_CONVERSATIONS", "5"))

        # Conversation
        self.conversation_max_count: int = int(os.getenv("CONVERSATION_MAX_COUNT", "100"))
        self.session_list_limit: int = int(os.getenv("SESSION_LIST_LIMIT", "50"))

        # Durable background jobs
        self.job_worker_poll_interval: float = float(os.getenv(
            "JOB_WORKER_POLL_INTERVAL", "0.5"
        ))
        self.job_payload_max_chars: int = int(os.getenv(
            "JOB_PAYLOAD_MAX_CHARS", "50000"
        ))
        self.job_result_max_chars: int = int(os.getenv(
            "JOB_RESULT_MAX_CHARS", "200000"
        ))
        self.job_default_max_attempts: int = int(os.getenv(
            "JOB_DEFAULT_MAX_ATTEMPTS", "3"
        ))
        self.job_retry_delay_seconds: int = int(os.getenv(
            "JOB_RETRY_DELAY_SECONDS", "5"
        ))

        # Reminders and scheduling
        self.reminder_default_timezone: str = os.getenv(
            "REMINDER_DEFAULT_TIMEZONE", "UTC"
        )
        self.reminder_message_max_chars: int = int(os.getenv(
            "REMINDER_MESSAGE_MAX_CHARS", "2000"
        ))
        self.reminder_min_interval_seconds: int = int(os.getenv(
            "REMINDER_MIN_INTERVAL_SECONDS", "60"
        ))
        self.reminder_reconcile_limit: int = int(os.getenv(
            "REMINDER_RECONCILE_LIMIT", "1000"
        ))

        # Persistent orchestration
        self.orchestration_task_max_chars: int = int(os.getenv(
            "ORCHESTRATION_TASK_MAX_CHARS", "10000"
        ))
        self.orchestration_result_max_chars: int = int(os.getenv(
            "ORCHESTRATION_RESULT_MAX_CHARS", "50000"
        ))
        self.orchestration_max_agents: int = int(os.getenv(
            "ORCHESTRATION_MAX_AGENTS", "8"
        ))
        self.orchestration_max_steps: int = int(os.getenv(
            "ORCHESTRATION_MAX_STEPS", "80"
        ))
        self.orchestration_max_team_turns: int = int(os.getenv(
            "ORCHESTRATION_MAX_TEAM_TURNS", "10"
        ))
        self.orchestration_step_max_attempts: int = int(os.getenv(
            "ORCHESTRATION_STEP_MAX_ATTEMPTS", "2"
        ))
        self.orchestration_job_max_attempts: int = int(os.getenv(
            "ORCHESTRATION_JOB_MAX_ATTEMPTS", "5"
        ))
        self.orchestration_reconcile_limit: int = int(os.getenv(
            "ORCHESTRATION_RECONCILE_LIMIT", "1000"
        ))

        # Tools / Web
        self.web_search_max_results: int = int(os.getenv("WEB_SEARCH_MAX_RESULTS", "5"))
        self.tool_calling_enabled: bool = os.getenv("TOOL_CALLING_ENABLED", "true").lower() == "true"
        self.tool_call_max_params_length: int = int(os.getenv("TOOL_CALL_MAX_PARAMS_LENGTH", "5000"))

        # Planner & Research
        self.plan_web_search_max_results: int = int(os.getenv("PLAN_WEB_SEARCH_MAX_RESULTS", "5"))
        self.plan_top_sources_count: int = int(os.getenv("PLAN_TOP_SOURCES_COUNT", "3"))
        self.crawl_content_max_chars: int = int(os.getenv("CRAWL_CONTENT_MAX_CHARS", "2000"))
        self.web_crawl_max_workers: int = int(os.getenv("WEB_CRAWL_MAX_WORKERS", "4"))
        self.web_crawl_max_urls: int = int(os.getenv("WEB_CRAWL_MAX_URLS", "10"))
        self.web_crawl_max_redirects: int = int(os.getenv("WEB_CRAWL_MAX_REDIRECTS", "5"))
        self.web_crawl_timeout: int = int(os.getenv("WEB_CRAWL_TIMEOUT", "15"))
        self.web_crawl_max_response_bytes: int = int(os.getenv(
            "WEB_CRAWL_MAX_RESPONSE_BYTES", "5000000"
        ))
        self.web_crawl_allow_private_network: bool = os.getenv(
            "WEB_CRAWL_ALLOW_PRIVATE_NETWORK", "false"
        ).lower() == "true"

        # Agent Loop
        self.agent_max_iterations: int = int(os.getenv("AGENT_MAX_ITERATIONS", "5"))
        self.agent_reflection_enabled: bool = os.getenv("AGENT_REFLECTION_ENABLED", "true").lower() == "true"
        self.orchestrator_max_workers: int = int(os.getenv(
            "ORCHESTRATOR_MAX_WORKERS", "4"
        ))

        # Background response work (startup-only executor sizing)
        self.background_max_workers: int = int(os.getenv(
            "BACKGROUND_MAX_WORKERS", "1"
        ))
        self.background_max_pending: int = int(os.getenv(
            "BACKGROUND_MAX_PENDING", "20"
        ))

        # Input Validation
        self.max_input_length: int = int(os.getenv("MAX_INPUT_LENGTH", "10000"))
        self.max_calculation_length: int = int(os.getenv("MAX_CALCULATION_LENGTH", "200"))

        # Tools
        self.file_search_root_path: str = os.getenv("FILE_SEARCH_ROOT_PATH", ".")
        self.file_read_encoding: str = os.getenv("FILE_READ_ENCODING", "utf-8")
        self.file_write_enabled: bool = os.getenv("FILE_WRITE_ENABLED", "true").lower() == "true"
        self.file_write_encoding: str = os.getenv("FILE_WRITE_ENCODING", "utf-8")
        self.file_delete_enabled: bool = os.getenv("FILE_DELETE_ENABLED", "true").lower() == "true"
        self.file_grep_max_results: int = int(os.getenv("FILE_GREP_MAX_RESULTS", "50"))
        self.file_search_max_results: int = int(os.getenv("FILE_SEARCH_MAX_RESULTS", "20"))
        self.file_scan_max_files: int = int(os.getenv("FILE_SCAN_MAX_FILES", "10000"))

        # Paths
        self.execution_log_path: str = os.getenv("EXECUTION_LOG_PATH", "logs/execution.log")
        self.memory_data_path: str = os.getenv("MEMORY_DATA_PATH", "data/memories")
        self.conversation_data_path: str = os.getenv("CONVERSATION_DATA_PATH", "data/conversations")

        # OS / Shell
        self.shell_enabled: bool = os.getenv("SHELL_ENABLED", "true").lower() == "true"
        self.shell_unsafe_enabled: bool = os.getenv(
            "SHELL_UNSAFE_ENABLED", "false"
        ).lower() == "true"
        self.shell_timeout: int = int(os.getenv("SHELL_TIMEOUT", "30"))
        self.shell_allowed_workdirs: list = [
            value.strip() for value in os.getenv(
                "SHELL_ALLOWED_WORKDIRS", "."
            ).split(",") if value.strip()
        ]
        self.shell_blocked_keywords: list = os.getenv(
            "SHELL_BLOCKED_KEYWORDS",
            "rm -rf,format,del /,shutdown,rd /s,del /f,format c:,diskpart"
        ).split(",")
        self.app_launcher_enabled: bool = os.getenv("APP_LAUNCHER_ENABLED", "true").lower() == "true"
        self.app_launcher_uwp_enabled: bool = os.getenv("APP_LAUNCHER_UWP_ENABLED", "true").lower() == "true"

        # Streaming
        self.streaming_enabled: bool = os.getenv("STREAMING_ENABLED", "true").lower() == "true"

        # Native tool calling
        self.native_tool_calling: bool = os.getenv("NATIVE_TOOL_CALLING", "true").lower() == "true"

        # Safety
        self.tool_call_confirm_high_permission: bool = os.getenv("TOOL_CALL_CONFIRM_HIGH", "true").lower() == "true"
        self.audit_log_enabled: bool = os.getenv("AUDIT_LOG_ENABLED", "true").lower() == "true"
        self.audit_log_path: str = os.getenv("AUDIT_LOG_PATH", "logs/audit.log")
        self.protected_paths: list = os.getenv(
            "PROTECTED_PATHS",
            ".env,.git,.gitignore,*.key,*.pem,*.env"
        ).split(",")

        # Persona
        self.persona_path: str = os.getenv("PERSONA_PATH", "src/config/persona.txt")

        # Logging
        self.log_level: str = os.getenv("LOG_LEVEL", "DEBUG")
        self.log_format: str = _validate_log_format(
            os.getenv("LOG_FORMAT", DEFAULT_LOG_FORMAT)
        )

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
