import uuid
import logging

from datetime import datetime, timezone

from database.db import db_session
from database.models import Conversation, Memory, Session
from config.settings import settings

logger = logging.getLogger(__name__)


class SessionRepository:

    def create(self, agent_id=None):
        session_id = uuid.uuid4().hex[:12]
        with db_session() as db:
            session = Session(id=session_id, agent_id=agent_id)
            db.add(session)
            db.flush()
            db.refresh(session)
            logger.info("Session created: %s (agent: %s)", session_id, agent_id)
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

    def get_all_sessions(self, agent_id=None, limit=None):
        if limit is None:
            limit = settings.session_list_limit
        limit = max(1, int(limit))
        with db_session() as db:
            query = db.query(Session).order_by(Session.last_active.desc())
            if agent_id:
                query = query.filter(
                    (Session.agent_id == agent_id) | (Session.agent_id.is_(None))
                )
            return query.limit(limit).all()

    def get_recent_with_summaries(self, limit=5, exclude_session_id=None, agent_id=None):
        with db_session() as db:
            query = (
                db.query(Session)
                .filter(Session.summary.isnot(None))
                .filter(Session.summary != "")
            )
            if exclude_session_id:
                query = query.filter(Session.id != exclude_session_id)
            if agent_id:
                query = query.filter(
                    (Session.agent_id == agent_id) | (Session.agent_id.is_(None))
                )
            return (
                query
                .order_by(Session.last_active.desc())
                .limit(limit)
                .all()
            )

    def delete(self, session_id):
        with db_session() as db:
            conversation_ids = (
                db.query(Conversation.id)
                .filter(Conversation.session_id == session_id)
            )
            memories_unlinked = (
                db.query(Memory)
                .filter(Memory.source_conversation_id.in_(conversation_ids))
                .update(
                    {Memory.source_conversation_id: None},
                    synchronize_session=False,
                )
            )
            conversation_count = (
                db.query(Conversation)
                .filter(Conversation.session_id == session_id)
                .delete(synchronize_session=False)
            )
            session_count = (
                db.query(Session)
                .filter(Session.id == session_id)
                .delete(synchronize_session=False)
            )
            return {
                "session_deleted": session_count == 1,
                "conversations_deleted": conversation_count,
                "memories_unlinked": memories_unlinked,
            }
