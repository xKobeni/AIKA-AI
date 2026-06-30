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
    "web": ["web_search_max_results"],
    "planner": ["plan_web_search_max_results", "plan_top_sources_count", "crawl_content_max_chars"],
    "validation": ["max_input_length", "max_calculation_length"],
    "tools": ["file_search_root_path", "file_read_encoding"],
    "paths": ["execution_log_path", "memory_data_path", "conversation_data_path"],
    "persona": ["persona_path"],
    "logging": ["log_level", "log_format"],
}


class ConfigHandler:

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

        setattr(settings, key, typed)
        logger.info("Setting %s changed: %s -> %s", key, old, typed)

        return f"{key} changed from {old} to {typed}. Use !save to persist."

    def _save(self):

        path = ".env"
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
                            new_lines.append(f"{k}={getattr(settings, attr_name)}\n")
                            updated.add(k)
                        else:
                            new_lines.append(line)
                    else:
                        new_lines.append(line)

        for env_name, attr_name in env_key_map.items():
            if env_name not in updated:
                new_lines.append(f"{env_name}={getattr(settings, attr_name)}\n")

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
            "max_input_length": "MAX_INPUT_LENGTH",
            "max_calculation_length": "MAX_CALCULATION_LENGTH",
            "file_search_root_path": "FILE_SEARCH_ROOT_PATH",
            "file_read_encoding": "FILE_READ_ENCODING",
            "execution_log_path": "EXECUTION_LOG_PATH",
            "memory_data_path": "MEMORY_DATA_PATH",
            "conversation_data_path": "CONVERSATION_DATA_PATH",
            "log_level": "LOG_LEVEL",
            "log_format": "LOG_FORMAT",
            "persona_path": "PERSONA_PATH",
        }

        return known_map.get(attr_name)

    def _cast(self, value, type_name):

        try:

            if type_name == "int":
                return int(value)

            if type_name == "float":
                return float(value)

            return value

        except ValueError:
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
            else:
                old = settings.smart_model
                settings.smart_model = model_name
            logger.info("Model %s switched: %s -> %s", tier, old, model_name)
            return (
                f"Model {tier}: {old} -> {model_name}\n"
                f"Next call will use the new model."
            )

        model_name = parts[1].strip()
        old = settings.chat_model
        settings.chat_model = model_name

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

        logger.info("Log level changed: %s -> %s", old, settings.log_level)

        return f"Log level changed: {old} -> {settings.log_level}"
