from database.db import db_session
from database.models import Conversation
from sqlalchemy import func
from config.settings import settings

class ConversationRepository:

    def __init__(self):
        self.max_count = settings.conversation_max_count
        self.recent_limit = settings.recent_conversations_count

    def create(self, role, content, session_id=None, tool_used=None,
               embedding=None, intent=None, model_used=None,
               response_time_ms=None, token_count=None):

        with db_session() as db:

            conversation = Conversation(
                role=role,
                content=content,
                session_id=session_id,
                tool_used=tool_used,
                embedding=embedding,
                intent=intent,
                model_used=model_used,
                response_time_ms=response_time_ms,
                token_count=token_count
            )

            db.add(conversation)
            db.flush()
            db.refresh(conversation)

            return conversation

    def get_recent(self, limit=None):

        if limit is None:
            limit = self.recent_limit

        with db_session() as db:

            conversations = (
                db.query(Conversation)
                .order_by(Conversation.id.desc())
                .limit(limit)
                .all()
            )

            return list(reversed(conversations))

    def get_by_session(self, session_id, limit=None):

        if limit is None:
            limit = self.recent_limit

        with db_session() as db:

            conversations = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .order_by(Conversation.id.desc())
                .limit(limit)
                .all()
            )

            return list(reversed(conversations))

    def semantic_search(self, query_embedding, limit=5):

        with db_session() as db:

            conversations = (
                db.query(Conversation)
                .filter(Conversation.embedding.isnot(None))
                .order_by(Conversation.embedding.l2_distance(query_embedding))
                .limit(limit)
                .all()
            )

            return list(reversed(conversations))

    def get_by_role(self, role, limit=10):

        with db_session() as db:

            conversations = (
                db.query(Conversation)
                .filter(Conversation.role == role)
                .order_by(Conversation.id.desc())
                .limit(limit)
                .all()
            )

            return list(reversed(conversations))

    def trim(self, max_count=None):

        if max_count is None:
            max_count = self.max_count

        with db_session() as db:

            count = db.query(func.count(Conversation.id)).scalar()

            if count > max_count:

                first_to_keep = (
                    db.query(Conversation.id)
                    .order_by(Conversation.id)
                    .offset(count - max_count)
                    .limit(1)
                    .scalar()
                )

                if first_to_keep is not None:

                    db.query(Conversation).filter(
                        Conversation.id < first_to_keep
                    ).delete(synchronize_session=False)

    def clear(self):

        with db_session() as db:

            db.query(Conversation).delete()