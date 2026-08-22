from dataclasses import dataclass


@dataclass
class ToolRequest:

    tool_name: str

    parameters: dict