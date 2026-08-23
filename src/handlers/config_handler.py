import os
import logging

from config.settings import settings

logger = logging.getLogger(__name__)

CATEGORIES = {
    "database": ["database_url"],
    "llm": ["chat_model", "embedding_model", "ollama_host", "llm_timeout"],
    "memory": ["memory_retrieval_limit", "memory_candidate_multiplier", "memory_min_score",
               "memory_recency_half_life_hours", "memory_sim_weight", "memory_importance_weight",
               "memory_profile_weight", "memory_access_weight", "memory_recency_weight",
               "memory_category_boost_project", "memory_category_boost_goal",
               "memory_category_boost_skill", "memory_max_per_category", "memory_validator_min_score"],
    "context": ["max_context_tokens", "max_profile_per_category", "recent_conversations_count"],
    "conversation": ["conversation_max_count"],
    "jobs": ["job_worker_poll_interval", "job_payload_max_chars",
             "job_result_max_chars", "job_default_max_attempts",
             "job_retry_delay_seconds"],
    "reminders": ["reminder_default_timezone", "reminder_message_max_chars",
                  "reminder_min_interval_seconds", "reminder_reconcile_limit"],
    "orchestration": ["orchestration_task_max_chars",
                      "orchestration_result_max_chars",
                      "orchestration_max_agents", "orchestration_max_steps",
                      "orchestration_max_team_turns",
                      "orchestration_step_max_attempts",
                      "orchestration_job_max_attempts",
                      "orchestration_reconcile_limit"],
    "web": ["web_search_max_results", "web_crawl_max_workers", "web_crawl_max_urls",
            "web_crawl_max_redirects", "web_crawl_timeout",
            "web_crawl_max_response_bytes", "web_crawl_allow_private_network"],
    "planner": ["plan_web_search_max_results", "plan_top_sources_count", "crawl_content_max_chars"],
    "validation": ["max_input_length", "max_calculation_length"],
    "tools": ["file_search_root_path", "file_read_encoding",
              "file_search_max_results", "file_scan_max_files"],
    "shell": ["shell_enabled", "shell_unsafe_enabled", "shell_timeout",
              "shell_allowed_workdirs", "shell_blocked_keywords"],
    "paths": ["execution_log_path", "memory_data_path", "conversation_data_path"],
    "persona": ["persona_path"],
    "logging": ["log_level", "log_format"],
}


class ConfigHandler:

    def __init__(self, agent_registry=None, refresh_callback=None):
        self.agent_registry = agent_registry
        self.refresh_callback = refresh_callback

    def _notify_refresh(self, changed_keys=None):
        if self.refresh_callback:
            self.refresh_callback(changed_keys=changed_keys)

    def handle(self, user_message: str):

        text = user_message.strip()

        if text == "!settings":

            return self._list_all()

        if text.startswith("!settings "):

            category = text[10:].strip().lower()

            return self._list_category(category)

        if text.startswith("!set "):

            rest = text[5:].strip()

            return self._set_value(rest)

        if text == "!save":

            return self._save()

        if text == "!reload":

            settings.reload()
            self._notify_refresh()
            logger.info("Settings reloaded from environment")
            return "Settings reloaded from environment."

        if text == "!persona":

            persona = settings.load_persona()
            if persona:
                return f"Current persona:\n\n{persona}"
            return "No persona file found."

        if text == "!persona reload":

            if os.path.exists(settings.persona_path):
                logger.info("Persona reloaded from %s", settings.persona_path)
                return "Persona reloaded."
            return f"Persona file not found: {settings.persona_path}"

        if text.startswith("!model"):

            return self._switch_model(text)

        if text.startswith("!log"):

            return self._toggle_log(text)

        return (
            "Unknown config command.\n"
            "Available: !settings [category], !set KEY=value, !save, !reload, "
            "!persona [reload], !model [name], !log [level]"
        )

    def _list_all(self):

        keys = [k for k in sorted(vars(settings).keys()) if not k.startswith("_")]
        return self._format_keys(keys)

    def _list_category(self, category):

        matched = CATEGORIES.get(category)

        if matched is None:

            available = ", ".join(sorted(CATEGORIES.keys()))
            return (
                f"Unknown category '{category}'.\n"
                f"Available categories: {available}"
            )

        return self._format_keys(matched)

    def _format_keys(self, keys):

        lines = []

        for key in keys:

            raw = getattr(settings, key, None)
            display = f"{key} = {raw}"
            lines.append(display)

        return "\n".join(lines)

    def _set_value(self, rest):

        if "=" not in rest:
            return "Usage: !set KEY=value"

        key, _, value = rest.partition("=")
        key = key.strip()
        value = value.strip()

        if not hasattr(settings, key):
            return f"Unknown setting: {key}"

        old = getattr(settings, key)
        typed = self._cast(value, type(old).__name__)

        if typed is None:
            return f"Cannot parse '{value}' as type {type(old).__name__}"

        validation_error = self._validate_value(key, typed)
        if validation_error:
            return validation_error

        setattr(settings, key, typed)
        self._notify_refresh(changed_keys={key})
        logger.info("Setting %s changed: %s -> %s", key, old, typed)

        return f"{key} changed from {old} to {typed}. Use !save to persist."

    def _save(self):

        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
            ".env"
        )
        keys = [k for k in vars(settings).keys() if not k.startswith("_")]

        env_key_map = {}
        for key in keys:
            env_name = self._to_env_name(key)
            if env_name:
                env_key_map[env_name] = key

        updated = set()
        new_lines = []

        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    stripped = line.strip()
                    if "=" in stripped and not stripped.startswith("#"):
                        k, _, _ = stripped.partition("=")
                        k = k.strip()
                        if k in env_key_map:
                            attr_name = env_key_map[k]
                            serialized = self._serialize_env_value(
                                getattr(settings, attr_name)
                            )
                            new_lines.append(f"{k}={serialized}\n")
                            updated.add(k)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

        for env_name, attr_name in env_key_map.items():
            if env_name not in updated:
                serialized = self._serialize_env_value(
                    getattr(settings, attr_name)
                )
                new_lines.append(f"{env_name}={serialized}\n")

        with open(path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)

        logger.info("Settings saved to %s", path)
        return f"Settings saved to {path}."

    def _to_env_name(self, attr_name):

        env_name = attr_name.upper()

        known_map = {
            "database_url": "DATABASE_URL",
            "chat_model": "CHAT_MODEL",
            "embedding_model": "EMBEDDING_MODEL",
            "ollama_host": "OLLAMA_HOST",
            "llm_timeout": "LLM_TIMEOUT",
            "memory_retrieval_limit": "MEMORY_RETRIEVAL_LIMIT",
            "memory_candidate_multiplier": "MEMORY_CANDIDATE_MULTIPLIER",
            "memory_min_score": "MEMORY_MIN_SCORE",
            "memory_recency_half_life_hours": "MEMORY_RECENCY_HALF_LIFE",
            "memory_sim_weight": "MEMORY_SIM_WEIGHT",
            "memory_importance_weight": "MEMORY_IMPORTANCE_WEIGHT",
            "memory_profile_weight": "MEMORY_PROFILE_WEIGHT",
            "memory_access_weight": "MEMORY_ACCESS_WEIGHT",
            "memory_recency_weight": "MEMORY_RECENCY_WEIGHT",
            "memory_category_boost_project": "MEMORY_BOOST_PROJECT",
            "memory_category_boost_goal": "MEMORY_BOOST_GOAL",
            "memory_category_boost_skill": "MEMORY_BOOST_SKILL",
            "memory_max_per_category": "MEMORY_MAX_PER_CATEGORY",
            "memory_validator_min_score": "MEMORY_VALIDATOR_MIN_SCORE",
            "max_context_tokens": "MAX_CONTEXT_TOKENS",
            "max_profile_per_category": "MAX_PROFILE_PER_CATEGORY",
            "recent_conversations_count": "RECENT_CONVERSATIONS_COUNT",
            "conversation_max_count": "CONVERSATION_MAX_COUNT",
            "web_search_max_results": "WEB_SEARCH_MAX_RESULTS",
            "plan_web_search_max_results": "PLAN_WEB_SEARCH_MAX_RESULTS",
            "plan_top_sources_count": "PLAN_TOP_SOURCES_COUNT",
            "crawl_content_max_chars": "CRAWL_CONTENT_MAX_CHARS",
            "web_crawl_max_workers": "WEB_CRAWL_MAX_WORKERS",
            "web_crawl_max_urls": "WEB_CRAWL_MAX_URLS",
            "web_crawl_max_redirects": "WEB_CRAWL_MAX_REDIRECTS",
            "web_crawl_timeout": "WEB_CRAWL_TIMEOUT",
            "web_crawl_max_response_bytes": "WEB_CRAWL_MAX_RESPONSE_BYTES",
            "web_crawl_allow_private_network": "WEB_CRAWL_ALLOW_PRIVATE_NETWORK",
            "max_input_length": "MAX_INPUT_LENGTH",
            "max_calculation_length": "MAX_CALCULATION_LENGTH",
            "file_search_root_path": "FILE_SEARCH_ROOT_PATH",
            "file_read_encoding": "FILE_READ_ENCODING",
            "file_search_max_results": "FILE_SEARCH_MAX_RESULTS",
            "file_scan_max_files": "FILE_SCAN_MAX_FILES",
            "shell_unsafe_enabled": "SHELL_UNSAFE_ENABLED",
            "shell_allowed_workdirs": "SHELL_ALLOWED_WORKDIRS",
            "execution_log_path": "EXECUTION_LOG_PATH",
            "memory_data_path": "MEMORY_DATA_PATH",
            "conversation_data_path": "CONVERSATION_DATA_PATH",
            "log_level": "LOG_LEVEL",
            "log_format": "LOG_FORMAT",
            "persona_path": "PERSONA_PATH",
        }

        return known_map.get(attr_name, env_name)

    def _serialize_env_value(self, value):
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, list):
            return ",".join(str(item).strip() for item in value)
        return str(value)

    def _cast(self, value, type_name):

        try:

            if type_name == "bool":
                normalized = value.strip().lower()
                if normalized in ("true", "yes", "1"):
                    return True
                if normalized in ("false", "no", "0"):
                    return False
                return None

            if type_name == "int":
                return int(value)

            if type_name == "float":
                return float(value)

            if type_name == "list":
                return [item.strip() for item in value.split(",") if item.strip()]

            return value

        except ValueError:
            return None

    def _validate_value(self, key, value):
        positive_integer_settings = {
            "agent_max_iterations", "conversation_max_count",
            "context_cross_session_conversations",
            "context_session_summaries_count", "crawl_content_max_chars",
            "file_grep_max_results", "file_search_max_results",
            "file_scan_max_files", "llm_timeout",
            "job_default_max_attempts", "job_payload_max_chars",
            "job_result_max_chars", "job_retry_delay_seconds",
            "reminder_message_max_chars", "reminder_min_interval_seconds",
            "reminder_reconcile_limit",
            "orchestration_task_max_chars", "orchestration_result_max_chars",
            "orchestration_max_agents", "orchestration_max_steps",
            "orchestration_max_team_turns",
            "orchestration_step_max_attempts",
            "orchestration_job_max_attempts",
            "orchestration_reconcile_limit",
            "max_calculation_length", "max_context_tokens",
            "max_input_length", "max_profile_per_category",
            "memory_candidate_multiplier", "memory_extraction_max_per_message",
            "memory_max_per_category", "memory_recency_half_life_hours",
            "memory_retrieval_limit", "plan_top_sources_count",
            "plan_web_search_max_results", "recent_conversations_count",
            "shell_timeout", "tool_call_max_params_length",
            "web_crawl_max_redirects", "web_crawl_max_response_bytes",
            "web_crawl_max_urls", "web_crawl_max_workers", "web_crawl_timeout",
            "web_search_max_results",
        }
        unit_interval_settings = {
            "memory_access_weight", "memory_importance_weight",
            "memory_min_score", "memory_profile_weight",
            "memory_recency_weight", "memory_sim_weight",
            "memory_validator_min_score", "memory_dedup_threshold",
        }
        positive_number_settings = {"job_worker_poll_interval"}

        if key in positive_integer_settings and value <= 0:
            return f"{key} must be greater than zero."
        if key in unit_interval_settings and not 0 <= value <= 1:
            return f"{key} must be between 0 and 1."
        if key in positive_number_settings and value <= 0:
            return f"{key} must be greater than zero."
        if key == "reminder_default_timezone":
            from reminders.recurrence import get_timezone

            try:
                get_timezone(value)
            except ValueError as exc:
                return str(exc)
        return None

    def _switch_model(self, text):

        parts = text.split(maxsplit=2)

        if len(parts) < 2 or not parts[1].strip():
            return (
                f"Models:\n"
                f"  fast:  {settings.fast_model}\n"
                f"  smart: {settings.smart_model}\n"
                f"  chat:  {settings.chat_model}\n\n"
                f"Usage:\n"
                f"  !model              — show current models\n"
                f"  !model <name>       — switch chat model\n"
                f"  !model fast <name>  — switch fast model\n"
                f"  !model smart <name> — switch smart model"
            )

        tier = parts[1].strip().lower()

        if tier in ("fast", "smart") and len(parts) >= 3:
            model_name = parts[2].strip()
            if tier == "fast":
                old = settings.fast_model
                settings.fast_model = model_name
                changed_key = "fast_model"
            else:
                old = settings.smart_model
                settings.smart_model = model_name
                changed_key = "smart_model"
            self._notify_refresh(changed_keys={changed_key})
            logger.info("Model %s switched: %s -> %s", tier, old, model_name)
            return (
                f"Model {tier}: {old} -> {model_name}\n"
                f"Next call will use the new model."
            )

        model_name = parts[1].strip()
        old = settings.chat_model
        settings.chat_model = model_name
        self._notify_refresh(changed_keys={"chat_model"})

        logger.info("Model switched: %s -> %s", old, model_name)

        return (
            f"Model switched: {old} -> {model_name}\n"
            f"Next LLM call will use the new model."
        )

    def _toggle_log(self, text):

        parts = text.split(maxsplit=1)

        if len(parts) < 2 or not parts[1].strip():
            current = settings.log_level
            return (
                f"Current log level: {current}\n"
                f"Usage: !log <level>\n"
                f"Levels: debug, info, warning, error"
            )

        level = parts[1].strip().lower()

        valid_levels = {"debug", "info", "warning", "error", "critical"}
        if level not in valid_levels:
            return (
                f"Invalid log level: {level}\n"
                f"Valid levels: {', '.join(sorted(valid_levels))}"
            )

        old = settings.log_level
        settings.log_level = level.upper()

        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, settings.log_level))

        for handler in root_logger.handlers:
            handler.setLevel(getattr(logging, settings.log_level))

        logging.getLogger("httpx").setLevel(getattr(logging, settings.log_level))
        logging.getLogger("httpcore").setLevel(getattr(logging, settings.log_level))

        logger.info("Log level changed: %s -> %s", old, settings.log_level)

        return f"Log level changed: {old} -> {settings.log_level}"
