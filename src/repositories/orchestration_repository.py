import uuid
from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from database.db import db_session
from database.models import OrchestrationRun, OrchestrationStep
from orchestration.types import OrchestrationStatus, OrchestrationStepStatus


TERMINAL_RUN_STATUSES = {
    OrchestrationStatus.COMPLETED.value,
    OrchestrationStatus.FAILED.value,
    OrchestrationStatus.CANCELLED.value,
}


def _utcnow():
    return datetime.now(timezone.utc)


class OrchestrationRepository:
    """Transactional state transitions for persistent orchestration runs."""

    def create(
        self,
        kind,
        task,
        agent_ids,
        step_specs,
        *,
        max_turns,
        allow_high_tools=False,
        step_max_attempts=2,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
    ):
        if idempotency_key:
            with db_session() as db:
                existing = (
                    db.query(OrchestrationRun)
                    .filter(
                        OrchestrationRun.idempotency_key == idempotency_key
                    )
                    .first()
                )
                if existing is not None:
                    return existing, False

        now = _utcnow()
        run_id = uuid.uuid4().hex
        step_ids = [uuid.uuid4().hex for _ in step_specs]
        run = OrchestrationRun(
            id=run_id,
            kind=kind,
            task=task,
            agent_ids=list(agent_ids),
            status=OrchestrationStatus.QUEUED.value,
            revision=1,
            allow_high_tools=bool(allow_high_tools),
            owner_id=owner_id,
            agent_id=agent_id,
            session_id=session_id,
            idempotency_key=idempotency_key,
            total_steps=len(step_specs),
            completed_steps=0,
            max_turns=max_turns,
            created_at=now,
            updated_at=now,
        )
        steps = []
        for position, spec in enumerate(step_specs):
            dependency_position = spec.get("depends_on_position")
            dependency_id = (
                step_ids[dependency_position]
                if dependency_position is not None else None
            )
            steps.append(OrchestrationStep(
                id=step_ids[position],
                run_id=run_id,
                position=position,
                agent_id=spec["agent_id"],
                turn=spec.get("turn"),
                depends_on_step_id=dependency_id,
                status=OrchestrationStepStatus.PENDING.value,
                attempt_count=0,
                max_attempts=step_max_attempts,
                created_at=now,
                updated_at=now,
            ))
        try:
            with db_session() as db:
                db.add(run)
                db.add_all(steps)
                db.flush()
                db.refresh(run)
                return run, True
        except IntegrityError:
            if not idempotency_key:
                raise
            with db_session() as db:
                existing = (
                    db.query(OrchestrationRun)
                    .filter(
                        OrchestrationRun.idempotency_key == idempotency_key
                    )
                    .first()
                )
                if existing is None:
                    raise
                return existing, False

    def get(self, run_id):
        with db_session() as db:
            return (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .first()
            )

    def list_runs(
        self,
        *,
        status=None,
        owner_id=None,
        agent_id=None,
        limit=50,
    ):
        limit = max(1, min(int(limit), 200))
        with db_session() as db:
            query = db.query(OrchestrationRun)
            if status is not None:
                query = query.filter(OrchestrationRun.status == status)
            if owner_id is not None:
                query = query.filter(OrchestrationRun.owner_id == owner_id)
            if agent_id is not None:
                query = query.filter(OrchestrationRun.agent_id == agent_id)
            return (
                query.order_by(OrchestrationRun.created_at.desc())
                .limit(limit)
                .all()
            )

    def list_nonterminal(self, limit=1000):
        limit = max(1, min(int(limit), 5000))
        with db_session() as db:
            return (
                db.query(OrchestrationRun)
                .filter(~OrchestrationRun.status.in_(TERMINAL_RUN_STATUSES))
                .order_by(OrchestrationRun.created_at.asc())
                .limit(limit)
                .all()
            )

    def list_steps(self, run_id):
        with db_session() as db:
            return (
                db.query(OrchestrationStep)
                .filter(OrchestrationStep.run_id == run_id)
                .order_by(OrchestrationStep.position.asc())
                .all()
            )

    def claim_job(self, run_id, revision, job_id):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if run is None:
                return "missing", None
            if run.status in TERMINAL_RUN_STATUSES:
                return "terminal", run
            if run.revision != revision:
                return "stale", run
            if run.current_job_id not in (None, job_id):
                return "stale", run
            run.current_job_id = job_id
            run.updated_at = now
            return "claimed", run

    def set_job(self, run_id, revision, job_id):
        action, _ = self.claim_job(run_id, revision, job_id)
        return action == "claimed"

    def mark_waiting_approval(self, run_id, revision, job_id):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if (
                run is None
                or run.revision != revision
                or run.current_job_id not in (None, job_id)
                or run.status in TERMINAL_RUN_STATUSES
            ):
                return False
            run.current_job_id = job_id
            run.status = OrchestrationStatus.WAITING_APPROVAL.value
            run.updated_at = now
            return True

    def mark_approved(self, run_id, revision, job_id):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if (
                run is None
                or run.revision != revision
                or run.current_job_id != job_id
                or run.status in TERMINAL_RUN_STATUSES
            ):
                return False
            run.approved_at = run.approved_at or now
            run.status = OrchestrationStatus.RUNNING.value
            run.started_at = run.started_at or now
            run.updated_at = now
            return True

    def prepare_resume(self, run_id, revision, job_id):
        """Return an interrupted running step to pending after approval."""
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if (
                run is None
                or run.revision != revision
                or run.current_job_id != job_id
                or run.status in TERMINAL_RUN_STATUSES
            ):
                return False
            running_steps = (
                db.query(OrchestrationStep)
                .filter(
                    OrchestrationStep.run_id == run_id,
                    OrchestrationStep.status
                    == OrchestrationStepStatus.RUNNING.value,
                )
                .with_for_update()
                .all()
            )
            for step in running_steps:
                if step.attempt_count >= step.max_attempts:
                    step.status = OrchestrationStepStatus.FAILED.value
                    step.error_type = "StepAttemptLimitExceeded"
                    step.finished_at = now
                    step.updated_at = now
                    run.status = OrchestrationStatus.FAILED.value
                    run.error_type = "StepAttemptLimitExceeded"
                    run.finished_at = now
                    run.updated_at = now
                    return False
                step.status = OrchestrationStepStatus.PENDING.value
                step.error_type = None
                step.updated_at = now
            run.status = OrchestrationStatus.RUNNING.value
            run.started_at = run.started_at or now
            run.updated_at = now
            return True

    def next_step(self, run_id):
        with db_session() as db:
            steps = (
                db.query(OrchestrationStep)
                .filter(OrchestrationStep.run_id == run_id)
                .order_by(OrchestrationStep.position.asc())
                .all()
            )
            completed_ids = {
                step.id
                for step in steps
                if step.status == OrchestrationStepStatus.COMPLETED.value
            }
            for step in steps:
                if step.status != OrchestrationStepStatus.PENDING.value:
                    continue
                if (
                    step.depends_on_step_id is None
                    or step.depends_on_step_id in completed_ids
                ):
                    return step
            return None

    def start_step(self, run_id, step_id, input_text):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            step = (
                db.query(OrchestrationStep)
                .filter(
                    OrchestrationStep.id == step_id,
                    OrchestrationStep.run_id == run_id,
                )
                .with_for_update()
                .first()
            )
            if (
                run is None
                or step is None
                or run.status in TERMINAL_RUN_STATUSES
                or step.status != OrchestrationStepStatus.PENDING.value
            ):
                return None
            if step.attempt_count >= step.max_attempts:
                step.status = OrchestrationStepStatus.FAILED.value
                step.error_type = "StepAttemptLimitExceeded"
                step.finished_at = now
                step.updated_at = now
                run.status = OrchestrationStatus.FAILED.value
                run.error_type = step.error_type
                run.finished_at = now
                run.updated_at = now
                return None
            if step.depends_on_step_id is not None:
                dependency = (
                    db.query(OrchestrationStep)
                    .filter(OrchestrationStep.id == step.depends_on_step_id)
                    .first()
                )
                if (
                    dependency is None
                    or dependency.status
                    != OrchestrationStepStatus.COMPLETED.value
                ):
                    return None
            step.status = OrchestrationStepStatus.RUNNING.value
            step.input_text = input_text
            step.attempt_count += 1
            step.error_type = None
            step.started_at = now
            step.updated_at = now
            run.status = OrchestrationStatus.RUNNING.value
            run.started_at = run.started_at or now
            run.updated_at = now
            db.flush()
            db.refresh(step)
            return step

    def complete_step(self, run_id, step_id, result_text):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            step = (
                db.query(OrchestrationStep)
                .filter(
                    OrchestrationStep.id == step_id,
                    OrchestrationStep.run_id == run_id,
                )
                .with_for_update()
                .first()
            )
            if (
                run is None
                or step is None
                or step.status != OrchestrationStepStatus.RUNNING.value
            ):
                return False
            step.status = OrchestrationStepStatus.COMPLETED.value
            step.result_text = result_text
            step.error_type = None
            step.finished_at = now
            step.updated_at = now
            run.completed_steps += 1
            run.updated_at = now
            return True

    def fail_step(self, run_id, step_id, error_type):
        now = _utcnow()
        safe_error = str(error_type)[:200]
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            step = (
                db.query(OrchestrationStep)
                .filter(
                    OrchestrationStep.id == step_id,
                    OrchestrationStep.run_id == run_id,
                )
                .with_for_update()
                .first()
            )
            if run is None or step is None:
                return False
            if step.status == OrchestrationStepStatus.RUNNING.value:
                step.status = OrchestrationStepStatus.FAILED.value
                step.error_type = safe_error
                step.finished_at = now
                step.updated_at = now
            db.query(OrchestrationStep).filter(
                OrchestrationStep.run_id == run_id,
                OrchestrationStep.status
                == OrchestrationStepStatus.PENDING.value,
            ).update(
                {
                    OrchestrationStep.status:
                        OrchestrationStepStatus.SKIPPED.value,
                    OrchestrationStep.updated_at: now,
                    OrchestrationStep.finished_at: now,
                },
                synchronize_session=False,
            )
            run.status = OrchestrationStatus.FAILED.value
            run.error_type = safe_error
            run.finished_at = now
            run.updated_at = now
            return True

    def complete_run(self, run_id, result, *, skip_remaining=False):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return False
            if skip_remaining:
                db.query(OrchestrationStep).filter(
                    OrchestrationStep.run_id == run_id,
                    OrchestrationStep.status
                    == OrchestrationStepStatus.PENDING.value,
                ).update(
                    {
                        OrchestrationStep.status:
                            OrchestrationStepStatus.SKIPPED.value,
                        OrchestrationStep.updated_at: now,
                        OrchestrationStep.finished_at: now,
                    },
                    synchronize_session=False,
                )
            run.status = OrchestrationStatus.COMPLETED.value
            run.result = result
            run.error_type = None
            run.finished_at = now
            run.updated_at = now
            return True

    def cancel(self, run_id, *, owner_id=None, agent_id=None):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if run is None:
                return False, None
            if owner_id is not None and run.owner_id != owner_id:
                return False, None
            if agent_id is not None and run.agent_id != agent_id:
                return False, None
            if run.status == OrchestrationStatus.CANCELLED.value:
                return True, run.current_job_id
            if run.status in {
                OrchestrationStatus.COMPLETED.value,
                OrchestrationStatus.FAILED.value,
            }:
                return False, None
            job_id = run.current_job_id
            db.query(OrchestrationStep).filter(
                OrchestrationStep.run_id == run_id,
                OrchestrationStep.status.in_([
                    OrchestrationStepStatus.PENDING.value,
                    OrchestrationStepStatus.RUNNING.value,
                ]),
            ).update(
                {
                    OrchestrationStep.status:
                        OrchestrationStepStatus.CANCELLED.value,
                    OrchestrationStep.updated_at: now,
                    OrchestrationStep.finished_at: now,
                },
                synchronize_session=False,
            )
            run.status = OrchestrationStatus.CANCELLED.value
            run.cancelled_at = now
            run.finished_at = now
            run.updated_at = now
            return True, job_id

    def mark_failed_from_job(self, run_id, error_type):
        now = _utcnow()
        safe_error = str(error_type)[:200]
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if run is None or run.status in TERMINAL_RUN_STATUSES:
                return False
            affected = (
                db.query(OrchestrationStep)
                .filter(
                    OrchestrationStep.run_id == run_id,
                    OrchestrationStep.status.in_([
                        OrchestrationStepStatus.RUNNING.value,
                        OrchestrationStepStatus.PENDING.value,
                    ]),
                )
                .order_by(OrchestrationStep.position.asc())
                .with_for_update()
                .all()
            )
            if affected:
                failed_step = affected[0]
                failed_step.status = OrchestrationStepStatus.FAILED.value
                failed_step.error_type = safe_error
                failed_step.finished_at = now
                failed_step.updated_at = now
                for step in affected[1:]:
                    step.status = OrchestrationStepStatus.SKIPPED.value
                    step.finished_at = now
                    step.updated_at = now
            run.status = OrchestrationStatus.FAILED.value
            run.error_type = safe_error
            run.finished_at = now
            run.updated_at = now
            return True

    def reset_failed_for_resume(
        self, run_id, *, owner_id=None, agent_id=None
    ):
        now = _utcnow()
        with db_session() as db:
            run = (
                db.query(OrchestrationRun)
                .filter(OrchestrationRun.id == run_id)
                .with_for_update()
                .first()
            )
            if run is None or run.status != OrchestrationStatus.FAILED.value:
                return None
            if owner_id is not None and run.owner_id != owner_id:
                return None
            if agent_id is not None and run.agent_id != agent_id:
                return None
            failed_steps = (
                db.query(OrchestrationStep)
                .filter(
                    OrchestrationStep.run_id == run_id,
                    OrchestrationStep.status
                    == OrchestrationStepStatus.FAILED.value,
                )
                .with_for_update()
                .all()
            )
            if not failed_steps:
                return None
            first_failed_position = min(step.position for step in failed_steps)
            for step in db.query(OrchestrationStep).filter(
                OrchestrationStep.run_id == run_id,
                OrchestrationStep.position >= first_failed_position,
            ).with_for_update().all():
                step.status = OrchestrationStepStatus.PENDING.value
                step.input_text = None
                step.result_text = None
                step.attempt_count = 0
                step.error_type = None
                step.started_at = None
                step.finished_at = None
                step.updated_at = now
            run.completed_steps = db.query(OrchestrationStep).filter(
                OrchestrationStep.run_id == run_id,
                OrchestrationStep.status
                == OrchestrationStepStatus.COMPLETED.value,
            ).count()
            run.status = OrchestrationStatus.QUEUED.value
            run.revision += 1
            run.current_job_id = None
            run.result = None
            run.error_type = None
            run.finished_at = None
            run.cancelled_at = None
            run.updated_at = now
            db.flush()
            db.refresh(run)
            return run
