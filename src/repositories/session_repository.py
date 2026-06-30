import uuid
import logging

from datetime import datetime, timezone

from database.db import db_session
from database.models import Session

logger = logging.getLogger(__name__)


class SessionRepository:

    def create(self):
        session_id = uuid.uuid4().hex[:12]
        with db_session() as db:
            session = Session(id=session_id)
            db.add(session)
            db.flush()
            db.refresh(session)
            logger.info("Session created: %s", session_id)
            return session

    def get(self, session_id):
        with db_session() as db:
            return db.query(Session).filter(Session.id == session_id).first()

    def update_last_active(self, session_id):
        with db_session() as db:
            db.query(Session).filter(Session.id == session_id).update(
                {"last_active": datetime.now(timezone.utc)}
            )

    def increment_message_count(self, session_id, count=1):
        with db_session() as db:
            session = db.query(Session).filter(Session.id == session_id).first()
            if session:
                session.message_count = Session.message_count + count

    def update_summary(self, session_id, summary):
        with db_session() as db:
            db.query(Session).filter(Session.id == session_id).update(
                {"summary": summary}
            )

    def get_all(self, limit=10):
        with db_session() as db:
            return (
                db.query(Session)
                .order_by(Session.last_active.desc())
                .limit(limit)
                .all()
            )

    def find_by_partial_id(self, partial):
        with db_session() as db:
            return (
                db.query(Session)
                .filter(Session.id.startswith(partial))
                .all()
            )

    def get_all_sessions(self):
        with db_session() as db:
            return (
                db.query(Session)
                .order_by(Session.last_active.desc())
                .all()
            )

    def delete(self, session_id):
        with db_session() as db:
            db.query(Session).filter(Session.id == session_id).delete()
