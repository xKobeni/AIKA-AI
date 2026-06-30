import ollama

from config.settings import settings
from models.actions import Action


class LLMIntentClassifier:

    SYSTEM_PROMPT = (
        "You are an intent classifier. "
        "Read the user's message and classify their intent. "
        "Reply with ONLY one word from this list:\n\n"
        "WEB_SEARCH - Asking for factual information, "
        "current events, definitions, news, lookups, "
        "or anything requiring internet search\n"
        "FILE_SEARCH - Asking to read, find, or inspect "
        "files, code, or source files in the project\n"
        "FILE_WRITE - Asking to create, write, save, "
        "or generate a file or document\n"
        "MEMORY_SEARCH - Asking about personal information, "
        "stored preferences, goals, projects, "
        "or previous conversations\n"
        "PLAN_EXECUTION - Wants research, analysis, "
        "summarization, investigation, "
        "or multi-step work\n"
        "CHAT - General conversation, greeting, "
        "opinion, casual talk, or unsure"
    )

    def __init__(self):
        self.model = settings.fast_model
        self._last_text = None
        self._last_result = None

    def classify(self, text):
        if text == self._last_text:
            return self._last_result

        response = ollama.chat(
            model=self.model,
            messages=[
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT
                },
                {
                    "role": "user",
                    "content": text
                }
            ]
        )

        intent = (
            response["message"]["content"]
            .strip().upper()
        )

        if intent == "WEB_SEARCH":
            result = {
                "action": Action.USE_TOOL,
                "tool_name": "web_search"
            }
        elif intent == "FILE_SEARCH":
            result = {
                "action": Action.USE_TOOL,
                "tool_name": "file_search"
            }
        elif intent == "FILE_WRITE":
            result = {
                "action": Action.USE_TOOL,
                "tool_name": "file_write"
            }
        elif intent == "MEMORY_SEARCH":
            result = {
                "action": Action.USE_TOOL,
                "tool_name": "memory_search"
            }
        elif intent == "PLAN_EXECUTION":
            result = {
                "action": Action.PLAN_EXECUTION,
                "tool_name": None
            }
        else:
            result = {
                "action": Action.CHAT,
                "tool_name": None
            }

        self._last_text = text
        self._last_result = result
        return result
