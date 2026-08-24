"""Conservative, shared prompt budgeting for every Ollama request path."""

from dataclasses import dataclass
import json


def count_tokens(text):
    """Return a conservative token estimate for prose and dense text alike."""
    text = str(text or "")
    if not text:
        return 0
    words = len(text.split())
    word_estimate = words * 1.3
    character_estimate = len(text) / 4
    return int(max(word_estimate, character_estimate)) + 1


@dataclass(frozen=True)
class PromptSection:
    key: str
    text: str
    priority: int = 0
    required: bool = False
    keep: str = "start"
    truncatable: bool = True
    value: object = None


class PromptBudgeter:
    """Fit text sections, chat messages, and tool schemas into one limit."""

    def __init__(self, max_tokens):
        self.max_tokens = self._normalize_limit(max_tokens)

    @staticmethod
    def _normalize_limit(value):
        if isinstance(value, bool) or not isinstance(value, int):
            return 6000
        return max(1, value)

    def set_limit(self, max_tokens):
        self.max_tokens = self._normalize_limit(max_tokens)

    @staticmethod
    def truncate_text(text, token_limit, *, keep="start"):
        """Clip by characters so dense URLs/non-whitespace text also fit."""
        text = str(text or "")
        token_limit = max(0, int(token_limit or 0))
        if token_limit <= 0 or not text:
            return ""
        if count_tokens(text) <= token_limit:
            return text

        prefix = "... " if keep == "end" else ""
        suffix = "" if keep == "end" else " ..."
        low, high = 0, len(text)
        best = ""
        while low <= high:
            middle = (low + high) // 2
            fragment = (
                text[-middle:].lstrip() if keep == "end" and middle else
                text[:middle].rstrip()
            )
            candidate = f"{prefix}{fragment}{suffix}" if fragment else ""
            if count_tokens(candidate) <= token_limit:
                best = candidate
                low = middle + 1
            else:
                high = middle - 1
        return best

    @staticmethod
    def _section_cost(text):
        # One extra token conservatively covers role/separator framing.
        return count_tokens(text) + 1 if text else 0

    def _allocate(self, sections):
        sections = [
            section for section in sections
            if str(section.text or "").strip()
        ]
        if not sections:
            return {}

        full_cost = sum(self._section_cost(section.text) for section in sections)
        if full_cost <= self.max_tokens:
            return {section.key: section.text for section in sections}

        selected = {}
        selected_costs = {}
        required = sorted(
            (section for section in sections if section.required),
            key=lambda section: (-section.priority, section.key),
        )
        remaining = self.max_tokens

        # Give every required section a fair initial reservation before allowing
        # any one oversized section to consume the complete prompt.
        if required:
            fair_share = max(1, remaining // len(required))
            for section in required:
                content_budget = max(0, fair_share - 1)
                fitted = self.truncate_text(
                    section.text,
                    content_budget,
                    keep=section.keep,
                )
                if fitted:
                    cost = self._section_cost(fitted)
                    selected[section.key] = fitted
                    selected_costs[section.key] = cost
                    remaining -= cost

            # Expand the most important required content first. Short current
            # requests and tool results therefore remain intact under pressure.
            for section in required:
                if remaining <= 0:
                    break
                current_cost = selected_costs.get(section.key, 0)
                target_content_budget = max(
                    0,
                    current_cost - 1 + remaining,
                )
                fitted = self.truncate_text(
                    section.text,
                    target_content_budget,
                    keep=section.keep,
                )
                new_cost = self._section_cost(fitted)
                increase = max(0, new_cost - current_cost)
                if increase <= remaining and fitted:
                    selected[section.key] = fitted
                    selected_costs[section.key] = new_cost
                    remaining -= increase

        optional = sorted(
            (section for section in sections if not section.required),
            key=lambda section: (-section.priority, section.key),
        )
        for section in optional:
            if remaining <= 1:
                break
            full_section_cost = self._section_cost(section.text)
            if full_section_cost <= remaining:
                selected[section.key] = section.text
                selected_costs[section.key] = full_section_cost
                remaining -= full_section_cost
                continue
            if not section.truncatable:
                continue
            fitted = self.truncate_text(
                section.text,
                remaining - 1,
                keep=section.keep,
            )
            if fitted:
                cost = self._section_cost(fitted)
                selected[section.key] = fitted
                selected_costs[section.key] = cost
                remaining -= cost

        return selected

    def budget_text_sections(self, sections, *, separator="\n\n"):
        selected = self._allocate(sections)
        return separator.join(
            selected[section.key]
            for section in sections
            if section.key in selected
        )

    @staticmethod
    def count_request(messages, tools=None):
        """Count message content and serialized tool definitions together."""
        total = 0
        for message in messages or []:
            total += count_tokens(message.get("content", "")) + 1
        for tool in tools or []:
            total += count_tokens(
                json.dumps(tool, ensure_ascii=False, sort_keys=True, default=str)
            ) + 1
        return total

    def budget_agent_request(
        self,
        system_sections,
        messages,
        tools=None,
        *,
        current_user_text="",
    ):
        """Budget the complete AgentLoop payload and reconstruct valid objects."""
        tools = list(tools or [])
        messages = list(messages or [])
        full_system = "\n".join(
            section.text for section in system_sections
            if str(section.text or "").strip()
        )
        full_messages = (
            [{"role": "system", "content": full_system}]
            if full_system
            else []
        ) + [dict(message) for message in messages]
        if self.count_request(full_messages, tools) <= self.max_tokens:
            return full_messages, tools

        items = list(system_sections)
        latest_tool_index = next(
            (
                index for index in range(len(messages) - 1, -1, -1)
                if messages[index].get("role") == "tool"
            ),
            None,
        )
        current_user_index = next(
            (
                index for index in range(len(messages) - 1, -1, -1)
                if messages[index].get("role") == "user"
                and str(messages[index].get("content", "")) == str(current_user_text)
            ),
            None,
        )
        if current_user_index is None:
            current_user_index = next(
                (
                    index for index in range(len(messages) - 1, -1, -1)
                    if messages[index].get("role") == "user"
                ),
                None,
            )

        for index, message in enumerate(messages):
            is_current_user = index == current_user_index
            is_latest_tool = index == latest_tool_index
            priority = 100 if is_current_user else 95 if is_latest_tool else 50 + index
            items.append(PromptSection(
                key=f"message:{index}",
                text=str(message.get("content", "") or ""),
                priority=priority,
                required=is_current_user or is_latest_tool,
                keep="start" if is_current_user else "end",
                value=dict(message),
            ))

        for index, tool in enumerate(tools):
            serialized = json.dumps(
                tool, ensure_ascii=False, sort_keys=True, default=str
            )
            items.append(PromptSection(
                key=f"tool:{index}",
                text=serialized,
                priority=80,
                truncatable=False,
                value=tool,
            ))

        selected = self._allocate(items)
        selected_system = [
            selected[section.key]
            for section in system_sections
            if section.key in selected
        ]
        budgeted_messages = (
            [{"role": "system", "content": "\n".join(selected_system)}]
            if selected_system
            else []
        )
        for index, message in enumerate(messages):
            key = f"message:{index}"
            if key not in selected:
                continue
            output = dict(message)
            output["content"] = selected[key]
            budgeted_messages.append(output)

        budgeted_tools = [
            tool for index, tool in enumerate(tools)
            if f"tool:{index}" in selected
        ]
        return budgeted_messages, budgeted_tools
