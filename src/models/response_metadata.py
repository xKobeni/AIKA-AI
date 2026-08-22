from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ResponseMetadata:
    text: str
    user_conversation_id: Optional[int]
    assistant_conversation_id: Optional[int]
    session_id: Optional[str]
    agent_id: Optional[str]
    model_used: Optional[str]
    response_time_ms: Optional[int] = None
    prompt_tokens: Optional[int] = None
    response_tokens: Optional[int] = None
