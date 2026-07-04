from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentProfile:
    id: str
    name: str
    persona_path: Optional[str] = None
    model: Optional[str] = None
    allowed_tools: Optional[list] = None
    max_iterations: int = 5
    is_active: bool = True
    role: Optional[str] = None
    delegates_to: Optional[list] = None

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "persona_path": self.persona_path,
            "model": self.model,
            "allowed_tools": self.allowed_tools,
            "max_iterations": self.max_iterations,
            "is_active": self.is_active,
            "role": self.role,
            "delegates_to": self.delegates_to,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            id=data["id"],
            name=data["name"],
            persona_path=data.get("persona_path"),
            model=data.get("model"),
            allowed_tools=data.get("allowed_tools"),
            max_iterations=data.get("max_iterations", 5),
            is_active=data.get("is_active", True),
            role=data.get("role"),
            delegates_to=data.get("delegates_to"),
        )
