import logging

from models.response_metadata import ResponseMetadata

logger = logging.getLogger(__name__)

EMPTY_RESPONSE_FALLBACK = (
    "I couldn't generate a response just now. Please try again."
)
GENERATION_ERROR_FALLBACK = (
    "I'm having trouble generating a response right now. Please try again."
)
STREAM_INTERRUPTION_FALLBACK = (
    "The response was interrupted before it could finish. Please try again."
)


def ensure_visible_response(response, fallback=EMPTY_RESPONSE_FALLBACK):
    """Return response text that is safe to deliver and persist."""
    text = str(response or "")
    return text if text.strip() else fallback


class ResponseFinalizer:
    """Owns response persistence, metrics, and retention for every delivery mode."""

    def __init__(self, conversation_repo, embedding_service=None, session_repo=None):
        self.conversation_repo = conversation_repo
        self.embedding_service = embedding_service
        self.session_repo = session_repo

    def finalize(
        self,
        response,
        *,
        user_conversation_id,
        session_id,
        agent_id,
        model_used=None,
        intent=None,
        tool_used=None,
        response_time_ms=None,
        prompt_tokens=None,
        response_tokens=None,
    ):
        response = ensure_visible_response(response)
        if not isinstance(response_tokens, int) or response_tokens < 1:
            response_tokens = max(1, len(response) // 4)

        response_embedding = None
        if self.embedding_service and response:
            try:
                response_embedding = self.embedding_service.generate_embedding(response)
            except Exception:
                logger.debug("Failed to generate response embedding", exc_info=True)

        assistant = self.conversation_repo.create(
            role="assistant",
            content=response,
            session_id=session_id,
            embedding=response_embedding,
            intent=intent,
            tool_used=tool_used,
            model_used=model_used,
            response_time_ms=response_time_ms,
            token_count=response_tokens,
            agent_id=agent_id,
        )

        if self.session_repo and session_id:
            self.session_repo.increment_message_count(session_id, 2)
            self.session_repo.update_last_active(session_id)

        self.conversation_repo.trim(agent_id=agent_id)

        return ResponseMetadata(
            text=response,
            user_conversation_id=user_conversation_id,
            assistant_conversation_id=getattr(assistant, "id", None),
            session_id=session_id,
            agent_id=agent_id,
            model_used=model_used,
            response_time_ms=response_time_ms,
            prompt_tokens=prompt_tokens,
            response_tokens=response_tokens,
        )
