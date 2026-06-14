from dataclasses import dataclass


@dataclass
class PlanStep:

    step_id: int

    tool_name: str

    parameters: dict

    description: str
