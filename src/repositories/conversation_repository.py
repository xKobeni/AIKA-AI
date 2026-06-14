from database.db import SessionLocal
from database.models import Conversation
from sqlalchemy import func

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

    def trim(self, max_count=100):

        db = SessionLocal()

        total = db.query(func.count(Conversation.id)).scalar()

        if total > max_count:

            to_delete = total - max_count

            db.query(Conversation).filter(
                Conversation.id.in_(
                    db.query(Conversation.id)
                    .order_by(Conversation.id)
                    .limit(to_delete)
                    .subquery()
                )
            ).delete(synchronize_session=False)

            db.commit()

        db.close()

    def clear(self):

        db = SessionLocal()

        db.query(Conversation).delete()

        db.commit()
        db.close()