import logging

import ollama

from config.settings import settings
from brain.common import FAIL_PHRASES

logger = logging.getLogger(__name__)


class ReflectionEngine:

    SYSTEM_PROMPT = (
        "You are a task completion evaluator. "
        "Your job is to decide if the user's request has been answered.\n\n"
        "RULES:\n"
        "- If the result contains a useful answer, information, or response "
        "to the user's question, reply DONE immediately.\n"
        "- A web search that returns articles/results is a success. DONE.\n"
        "- A file read that returns content is a success. DONE.\n"
        "- A tool that returned a meaningful result is a success. DONE.\n"
        "- ONLY say NEXT if the action completely failed or the result "
        "is clearly insufficient to answer the question.\n"
        "- NEVER suggest follow-up work or ask the user for clarification. "
        "The system handles that on its own.\n\n"
        "Reply with EXACTLY one of:\n"
        "DONE\n"
        "NEXT: <what failed or is missing>"
    )

    def __init__(self):
        self.model = settings.fast_model

    def reflect(self, original_message, action_history, latest_result):
        result_text = str(latest_result).lower()

        if any(phrase in result_text for phrase in FAIL_PHRASES):
            logger.debug("Reflection: fail-fast (result contains error/empty)")
            return {"done": True, "next_action": None}

        prompt = (
            f"Original request: {original_message}\n\n"
            f"Actions already taken:\n{action_history}\n\n"
            f"Latest result:\n{str(latest_result)[:500]}\n\n"
            f"Is the task complete?"
        )

        try:
            response = ollama.chat(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.SYSTEM_PROMPT},
                    {"role": "user", "content": prompt}
                ]
            )

            text = response["message"]["content"].strip()
            logger.debug("Reflection: %s", text)

            if text.upper().startswith("DONE"):
                return {"done": True, "next_action": None}

            if text.upper().startswith("NEXT:"):
                next_step = text[5:].strip()
                return {"done": False, "next_action": next_step}

            return {"done": True, "next_action": None}

        except Exception as e:
            logger.warning("Reflection failed: %s", e)
            return {"done": True, "next_action": None}
