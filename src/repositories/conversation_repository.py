from database.db import db_session
from database.models import Conversation
from sqlalchemy import func
from config.settings import settings

class ConversationRepository:

    def __init__(self):
        self.max_count = settings.conversation_max_count
        self.recent_limit = settings.recent_conversations_count

    def create(self, role, content):

        with db_session() as db:

            conversation = Conversation(
                role=role,
                content=content
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

            # reverse so it's chronological
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