from database.db import SessionLocal
from database.models import Conversation

class ConversationRepository:

    def create(self, role, content):

        db = SessionLocal()

        conversation = Conversation(
            role=role,
            content=content
        )

        db.add(conversation)
        db.commit()
        db.refresh(conversation)

        db.close()

        return conversation

    def get_recent(self, limit=10):

        db = SessionLocal()

        conversations = (
            db.query(Conversation)
            .order_by(Conversation.id.desc())
            .limit(limit)
            .all()
        )

        db.close()

        # reverse so it's chronological
        return list(reversed(conversations))

    def clear(self):

        db = SessionLocal()

        db.query(Conversation).delete()

        db.commit()
        db.close()