import json

FAIL_PHRASES = [
    "no search results",
    "no results found",
    "error",
    "failed",
    "couldn't find",
    "not available",
    "not found",
    "access denied",
]


class AgentContext:

    def __init__(self, original_message):
        self.original_message = original_message
        self.iterations = 0
        self.messages = []
        self.actions_taken = []
        self.final_response = ""
        self.is_done = False

    def _is_failure(self, result):
        text = str(result).lower()
        return any(phrase in text for phrase in FAIL_PHRASES)

    def add_user_message(self, message):
        self.messages.append({"role": "user", "content": message})

    def add_iteration(self, action, tool_name, result):
        self.iterations += 1
        action_value = action.value if hasattr(action, "value") else str(action)
        self.actions_taken.append({
            "iteration": self.iterations,
            "action": action_value,
            "tool": tool_name,
            "parameters": {},
            "result": str(result)[:500],
            "failed": self._is_failure(result),
        })
        self.final_response = str(result)

    def add_tool_call(self, tool_name, parameters):
        self.actions_taken.append({
            "iteration": self.iterations,
            "action": "USE_TOOL",
            "tool": tool_name,
            "parameters": parameters,
            "result": "",
            "failed": False,
        })

    def add_tool_result(self, tool_name, result):
        self.iterations += 1
        if self.actions_taken:
            last = self.actions_taken[-1]
            last["result"] = str(result)[:500]
            last["failed"] = self._is_failure(result)

        self.messages.append({
            "role": "tool",
            "content": str(result)[:4000],
            "tool_name": tool_name,
        })

    def add_assistant_response(self, text):
        self.final_response = text
        self.messages.append({"role": "assistant", "content": text})
    def get_history_for_llm(self):
        if not self.actions_taken:
            return "No actions taken yet."

        lines = []
        for entry in self.actions_taken:
            tool_str = f" (tool: {entry['tool']})" if entry.get("tool") else ""
            lines.append(
                f"  {entry['iteration']}. {entry['action']}{tool_str}\n"
                f"     Result: {entry['result'][:200]}"
            )
        return "\n".join(lines)

    def get_history_as_list(self):
        if not self.actions_taken:
            return []
        return [
            {
                "iteration": h["iteration"],
                "action": h["action"],
                "tool": h.get("tool"),
                "result": h["result"][:200],
                "failed": h["failed"],
            }
            for h in self.actions_taken
        ]

    def get_enriched_input(self, user_message):
        if not self.actions_taken:
            return user_message

        history = self.get_history_for_llm()
        failed_actions = [
            e["action"] for e in self.actions_taken if e["failed"]
        ]
        avoid = ""
        if failed_actions:
            unique = list(dict.fromkeys(failed_actions))
            avoid = (
                f"\nDo NOT try these actions again (they already failed): "
                f"{', '.join(unique)}"
            )

        return (
            f"{user_message}\n\n"
            f"[Previous actions this session:]\n{history}\n\n"
            f"Do NOT repeat actions already taken above. "
            f"If the task is complete, respond normally.{avoid}"
        )

    def is_last_action_repeated_and_failed(self):
        if len(self.actions_taken) < 2:
            return False
        last = self.actions_taken[-1]
        prev = self.actions_taken[-2]
        same_action = last["action"] == prev["action"]
        same_tool = last.get("tool") == prev.get("tool")
        return (
            same_action
            and same_tool
            and last["failed"]
            and prev["failed"]
        )

    def get_action_count(self, action_type, tool_name=None):
        count = 0
        for entry in self.actions_taken:
            if entry["action"] == action_type:
                if tool_name is None or entry.get("tool") == tool_name:
                    count += 1
        return count
