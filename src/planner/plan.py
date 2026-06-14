from dataclasses import dataclass

from planner.plan_step import PlanStep


@dataclass
class Plan:

    goal: str

    steps: list[PlanStep]
