import json
import logging
import re
import uuid

from config.settings import settings
from jobs.types import JobCancelled, JobDefinition, NonRetryableJobError
from orchestration.types import (
    OrchestrationKind,
    OrchestrationStatus,
    OrchestrationStepStatus,
)
from repositories.orchestration_repository import OrchestrationRepository
from security.redaction import redact_sensitive


ORCHESTRATION_JOB_TYPE = "orchestration.execute"
TEAM_DONE_MARKER = "[TEAM_DONE]"
_HEX_ID = re.compile(r"^[0-9a-f]{32}$")
_TERMINAL_JOB_STATUSES = {"succeeded", "failed", "cancelled"}
logger = logging.getLogger(__name__)


class OrchestrationStepFailed(NonRetryableJobError):
    pass


def _bounded_identifier(value, label, maximum):
    if value is None:
        return None
    value = str(value).strip()
    if not value:
        return None
    if len(value) > maximum:
        raise ValueError(f"{label} exceeds {maximum} characters")
    return value


def validate_orchestration_job_payload(payload):
    run_id = payload.get("run_id")
    revision = payload.get("revision")
    if not isinstance(run_id, str) or not _HEX_ID.fullmatch(run_id):
        raise ValueError("run_id must be a 32-character lowercase hex ID")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        raise ValueError("revision must be a positive integer")
    return {"run_id": run_id, "revision": revision}


class PersistentOrchestrator:
    """Executes persisted orchestration steps through one non-retry-safe job."""

    def __init__(
        self,
        job_runtime,
        agent_registry,
        execute_step,
        repository=None,
        *,
        task_max_chars=None,
        result_max_chars=None,
        max_agents=None,
        max_steps=None,
        max_team_turns=None,
        step_max_attempts=None,
        job_max_attempts=None,
        reconcile_limit=None,
    ):
        if not callable(execute_step):
            raise TypeError("orchestration step executor must be callable")
        self.job_runtime = job_runtime
        self.agent_registry = agent_registry
        self.execute_step = execute_step
        self.repository = repository or OrchestrationRepository()
        self.task_max_chars = int(
            task_max_chars
            if task_max_chars is not None
            else settings.orchestration_task_max_chars
        )
        self.result_max_chars = int(
            result_max_chars
            if result_max_chars is not None
            else settings.orchestration_result_max_chars
        )
        self.max_agents = int(
            max_agents
            if max_agents is not None else settings.orchestration_max_agents
        )
        self.max_steps = int(
            max_steps
            if max_steps is not None else settings.orchestration_max_steps
        )
        self.max_team_turns = int(
            max_team_turns
            if max_team_turns is not None
            else settings.orchestration_max_team_turns
        )
        self.step_max_attempts = int(
            step_max_attempts
            if step_max_attempts is not None
            else settings.orchestration_step_max_attempts
        )
        self.job_max_attempts = int(
            job_max_attempts
            if job_max_attempts is not None
            else settings.orchestration_job_max_attempts
        )
        self.reconcile_limit = int(
            reconcile_limit
            if reconcile_limit is not None
            else settings.orchestration_reconcile_limit
        )
        if min(
            self.task_max_chars,
            self.result_max_chars,
            self.max_agents,
            self.max_steps,
            self.max_team_turns,
            self.step_max_attempts,
            self.job_max_attempts,
            self.reconcile_limit,
        ) <= 0:
            raise ValueError("orchestration limits must be positive")
        self._started = False
        self._notification_handler = None

    def set_notification_handler(self, handler):
        if handler is not None and not callable(handler):
            raise TypeError("orchestration notification handler must be callable")
        self._notification_handler = handler

    def _notify(self, run):
        if self._notification_handler is None:
            return
        try:
            self._notification_handler(self._run_to_dict(run, include_steps=False))
        except Exception as exc:
            logger.warning(
                "Orchestration notification handler failed: %s",
                type(exc).__name__,
            )

    def start(self):
        if self._started:
            return False
        self.job_runtime.register(JobDefinition(
            ORCHESTRATION_JOB_TYPE,
            self._execute_run,
            validator=validate_orchestration_job_payload,
            retry_safe=False,
            max_attempts=self.job_max_attempts,
        ))
        self._started = True
        self.reconcile()
        return True

    @staticmethod
    def _job_key(run):
        return f"orchestration:{run.id}:{run.revision}"

    def _ensure_job(self, run):
        if run is None or run.status in {
            OrchestrationStatus.COMPLETED.value,
            OrchestrationStatus.FAILED.value,
            OrchestrationStatus.CANCELLED.value,
        }:
            return None
        job, _ = self.job_runtime.enqueue(
            ORCHESTRATION_JOB_TYPE,
            {"run_id": run.id, "revision": run.revision},
            owner_id=run.owner_id,
            agent_id=run.agent_id,
            session_id=run.session_id,
            idempotency_key=self._job_key(run),
        )
        if job["status"] in _TERMINAL_JOB_STATUSES:
            self.repository.mark_failed_from_job(
                run.id, "TerminalJobForActiveRun"
            )
            return job
        self.repository.set_job(run.id, run.revision, job["id"])
        return job

    def reconcile(self):
        checked = 0
        scheduled = 0
        waiting = 0
        failed = 0
        for run in self.repository.list_nonterminal(self.reconcile_limit):
            checked += 1
            if not run.current_job_id:
                if self._ensure_job(run) is not None:
                    scheduled += 1
                continue
            job = self.job_runtime.get_job(run.current_job_id)
            if job is None:
                if self._ensure_job(run) is not None:
                    scheduled += 1
            elif job["status"] == "waiting_approval":
                if self.repository.mark_waiting_approval(
                    run.id, run.revision, job["id"]
                ):
                    waiting += 1
            elif job["status"] == "failed":
                if self.repository.mark_failed_from_job(
                    run.id, job.get("error_type") or "JobFailed"
                ):
                    failed += 1
            elif job["status"] == "cancelled":
                self.repository.cancel(run.id)
            elif job["status"] == "succeeded":
                if self.repository.mark_failed_from_job(
                    run.id, "InconsistentSucceededJob"
                ):
                    failed += 1
        return {
            "checked": checked,
            "scheduled": scheduled,
            "waiting_approval": waiting,
            "failed": failed,
        }

    def _normalize_agents(self, agent_ids):
        if not isinstance(agent_ids, (list, tuple)) or not agent_ids:
            raise ValueError("agent_ids must be a non-empty list")
        if len(agent_ids) > self.max_agents:
            raise ValueError(
                f"orchestration exceeds the {self.max_agents} agent limit"
            )
        normalized = []
        for value in agent_ids:
            agent_id = _bounded_identifier(value, "agent_id", 50)
            if agent_id is None:
                raise ValueError("agent IDs must be non-empty")
            profile = self.agent_registry.get(agent_id)
            if profile is None or not getattr(profile, "is_active", True):
                raise ValueError(f"agent is not available: {agent_id}")
            normalized.append(agent_id)
        return normalized

    @staticmethod
    def _step_specs(kind, agent_ids, max_turns):
        if kind == OrchestrationKind.TEAM.value:
            specs = []
            for turn in range(max_turns):
                for agent_id in agent_ids:
                    position = len(specs)
                    specs.append({
                        "agent_id": agent_id,
                        "turn": turn,
                        "depends_on_position": position - 1 if position else None,
                    })
            return specs
        return [
            {
                "agent_id": agent_id,
                "turn": None,
                "depends_on_position": (
                    position - 1
                    if kind == OrchestrationKind.CHAIN.value and position
                    else None
                ),
            }
            for position, agent_id in enumerate(agent_ids)
        ]

    def create_run(
        self,
        kind,
        agent_ids,
        task,
        *,
        max_turns=1,
        allow_high_tools=False,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
    ):
        try:
            kind = OrchestrationKind(str(kind).strip().lower()).value
        except ValueError as exc:
            raise ValueError(
                "orchestration kind must be delegate, chain, parallel, or team"
            ) from exc
        task = str(task).strip() if task is not None else ""
        if not task:
            raise ValueError("orchestration task must be non-empty")
        task = redact_sensitive(task)
        if len(task) > self.task_max_chars:
            raise ValueError(
                f"orchestration task exceeds {self.task_max_chars} characters"
            )
        agent_ids = self._normalize_agents(agent_ids)
        if kind == OrchestrationKind.DELEGATE.value and len(agent_ids) != 1:
            raise ValueError("delegate orchestration requires exactly one agent")
        if isinstance(max_turns, bool) or not isinstance(max_turns, int):
            raise ValueError("max_turns must be an integer")
        if kind == OrchestrationKind.TEAM.value:
            if not 1 <= max_turns <= self.max_team_turns:
                raise ValueError(
                    f"team turns must be between 1 and {self.max_team_turns}"
                )
        else:
            max_turns = 1
        specs = self._step_specs(kind, agent_ids, max_turns)
        if len(specs) > self.max_steps:
            raise ValueError(
                f"orchestration exceeds the {self.max_steps} step limit"
            )
        safe_owner = _bounded_identifier(owner_id, "owner_id", 100)
        safe_agent = _bounded_identifier(agent_id, "agent_id", 50)
        safe_session = _bounded_identifier(session_id, "session_id", 50)
        safe_key = _bounded_identifier(
            idempotency_key, "idempotency_key", 200
        )
        run, created = self.repository.create(
            kind,
            task,
            agent_ids,
            specs,
            max_turns=max_turns,
            allow_high_tools=bool(allow_high_tools),
            step_max_attempts=self.step_max_attempts,
            owner_id=safe_owner,
            agent_id=safe_agent,
            session_id=safe_session,
            idempotency_key=safe_key,
        )
        if not created and (
            run.owner_id != safe_owner
            or run.agent_id != safe_agent
            or run.kind != kind
        ):
            raise ValueError(
                "idempotency key belongs to a different orchestration scope"
            )
        self._ensure_job(run)
        return self._run_to_dict(run), created

    def _build_step_input(self, run, step, steps):
        if run.kind in {
            OrchestrationKind.DELEGATE.value,
            OrchestrationKind.PARALLEL.value,
        } or step.position == 0:
            return run.task
        completed = [
            item
            for item in steps
            if item.status == OrchestrationStepStatus.COMPLETED.value
            and item.position < step.position
        ]
        if run.kind == OrchestrationKind.CHAIN.value:
            previous = completed[-1]
            return (
                f"Previous result from {previous.agent_id}:\n"
                f"{previous.result_text}\n\nContinue with the next step."
            )
        recent = completed[-5:]
        parts = [
            f"You are part of a team working on: {run.task}",
            f"Team members: {', '.join(run.agent_ids)}",
            f"Current turn: {(step.turn or 0) + 1}",
            "",
            "Your role is to contribute to this task based on your expertise.",
            "Use the previous contributions below to continue the work.",
            "When the task is fully complete, end your response with [TEAM_DONE].",
            "",
            "Previous contributions:",
        ]
        if recent:
            for contribution in recent:
                preview = (contribution.result_text or "")[:200]
                parts.append(f"  [{contribution.agent_id}]: {preview}")
        else:
            parts.append("  (No contributions yet - you're starting!)")
        parts.extend(["", "Your contribution:"])
        return "\n".join(parts)

    def _bounded_result(self, value):
        result = redact_sensitive(str(value if value is not None else ""))
        if len(result) > self.result_max_chars:
            suffix = "\n[truncated]"
            if self.result_max_chars > len(suffix):
                result = (
                    result[: self.result_max_chars - len(suffix)] + suffix
                )
            else:
                result = result[: self.result_max_chars]
        return result

    def _bounded_input(self, value):
        limit = self.task_max_chars + self.result_max_chars
        text = str(value)
        return text if len(text) <= limit else text[:limit]

    def _assemble_result(self, run, steps):
        completed = [
            step
            for step in steps
            if step.status == OrchestrationStepStatus.COMPLETED.value
        ]
        if run.kind == OrchestrationKind.PARALLEL.value:
            result = {
                "results": [
                    {"agent": step.agent_id, "result": step.result_text or ""}
                    for step in completed
                ]
            }
        elif run.kind == OrchestrationKind.TEAM.value:
            result = {
                "text": "\n\n".join(
                    f"[{step.agent_id}]: {step.result_text or ''}"
                    for step in completed
                )
            }
        else:
            result = {"text": completed[-1].result_text if completed else ""}
        serialized = json.dumps(result, ensure_ascii=False)
        if len(serialized) <= self.result_max_chars:
            return result
        text = result.get("text", serialized)
        return {
            "text": str(text)[: self.result_max_chars],
            "truncated": True,
        }

    def _execute_run(self, context, payload):
        run_id = payload["run_id"]
        revision = payload["revision"]
        action, run = self.repository.claim_job(
            run_id, revision, context.job_id
        )
        if action != "claimed":
            return {"action": action, "run_id": run_id}
        try:
            context.check_cancelled()
            if run.allow_high_tools and run.approved_at is None:
                if not context.approval_granted:
                    self.repository.mark_waiting_approval(
                        run_id, revision, context.job_id
                    )
                    context.require_approval({
                        "reason": "orchestration_high_permission_tools",
                        "run_id": run_id,
                        "kind": run.kind,
                        "agents": run.agent_ids,
                        "task_preview": run.task[:200],
                        "message": (
                            "Approve this persistent orchestration to allow "
                            "its agents to execute high-permission tools."
                        ),
                    })
                self.repository.mark_approved(
                    run_id, revision, context.job_id
                )
            if not self.repository.prepare_resume(
                run_id, revision, context.job_id
            ):
                current = self.repository.get(run_id)
                if current is not None and current.status in {
                    OrchestrationStatus.FAILED.value,
                    OrchestrationStatus.CANCELLED.value,
                }:
                    raise OrchestrationStepFailed(
                        current.error_type or "OrchestrationCannotResume"
                    )

            while True:
                context.check_cancelled()
                run = self.repository.get(run_id)
                steps = self.repository.list_steps(run_id)
                step = self.repository.next_step(run_id)
                if step is None:
                    if any(item.status in {
                        OrchestrationStepStatus.PENDING.value,
                        OrchestrationStepStatus.RUNNING.value,
                    } for item in steps):
                        self.repository.mark_failed_from_job(
                            run_id, "OrchestrationDependencyDeadlock"
                        )
                        raise OrchestrationStepFailed(
                            "OrchestrationDependencyDeadlock"
                        )
                    result = self._assemble_result(run, steps)
                    self.repository.complete_run(run_id, result)
                    completed = self.repository.get(run_id)
                    self._notify(completed)
                    return {
                        "action": "completed",
                        "run_id": run_id,
                        "completed_steps": completed.completed_steps,
                    }

                input_text = self._bounded_input(
                    self._build_step_input(run, step, steps)
                )
                started = self.repository.start_step(
                    run_id, step.id, input_text
                )
                if started is None:
                    raise OrchestrationStepFailed("OrchestrationStepUnavailable")
                progress = int(
                    100 * run.completed_steps / max(1, run.total_steps)
                )
                context.set_progress(progress, {
                    "run_id": run_id,
                    "step": step.position,
                    "agent_id": step.agent_id,
                })
                try:
                    output = self.execute_step(
                        step.agent_id,
                        input_text,
                        allow_high_tools=bool(run.allow_high_tools),
                    )
                    context.check_cancelled()
                except JobCancelled:
                    raise
                except Exception as exc:
                    self.repository.fail_step(
                        run_id, step.id, type(exc).__name__
                    )
                    raise OrchestrationStepFailed(
                        type(exc).__name__
                    ) from exc
                output = self._bounded_result(output)
                if not self.repository.complete_step(run_id, step.id, output):
                    raise OrchestrationStepFailed(
                        "OrchestrationStepCommitFailed"
                    )
                if (
                    run.kind == OrchestrationKind.TEAM.value
                    and TEAM_DONE_MARKER in output
                ):
                    steps = self.repository.list_steps(run_id)
                    result = self._assemble_result(run, steps)
                    self.repository.complete_run(
                        run_id, result, skip_remaining=True
                    )
                    completed = self.repository.get(run_id)
                    self._notify(completed)
                    return {
                        "action": "completed",
                        "run_id": run_id,
                        "completed_steps": completed.completed_steps,
                        "team_done": True,
                    }
        except JobCancelled:
            self.repository.cancel(run_id)
            cancelled = self.repository.get(run_id)
            if cancelled is not None:
                self._notify(cancelled)
            raise

    def get_run(
        self, run_id, *, owner_id=None, agent_id=None, include_steps=True
    ):
        run = self.repository.get(str(run_id))
        if run is None:
            return None
        if owner_id is not None and run.owner_id != owner_id:
            return None
        if agent_id is not None and run.agent_id != agent_id:
            return None
        return self._run_to_dict(run, include_steps=include_steps)

    def list_runs(self, **filters):
        return [
            self._run_to_dict(run, include_steps=False)
            for run in self.repository.list_runs(**filters)
        ]

    def cancel_run(self, run_id, *, owner_id=None, agent_id=None):
        changed, job_id = self.repository.cancel(
            str(run_id), owner_id=owner_id, agent_id=agent_id
        )
        if changed and job_id:
            self.job_runtime.cancel_job(job_id)
        return changed

    def resolve_approval(
        self, run_id, approved, *, owner_id=None, agent_id=None
    ):
        run = self.repository.get(str(run_id))
        if run is None:
            return False
        if owner_id is not None and run.owner_id != owner_id:
            return False
        if agent_id is not None and run.agent_id != agent_id:
            return False
        if (
            run.status != OrchestrationStatus.WAITING_APPROVAL.value
            or not run.current_job_id
        ):
            return False
        changed = self.job_runtime.resolve_job_approval(
            run.current_job_id, bool(approved)
        )
        if changed and not approved:
            self.repository.cancel(run.id)
        return changed

    def resume_run(self, run_id, *, owner_id=None, agent_id=None):
        run = self.repository.get(str(run_id))
        if run is None:
            return False
        if owner_id is not None and run.owner_id != owner_id:
            return False
        if agent_id is not None and run.agent_id != agent_id:
            return False
        if run.status == OrchestrationStatus.WAITING_APPROVAL.value:
            return self.resolve_approval(
                run.id,
                True,
                owner_id=owner_id,
                agent_id=agent_id,
            )
        if run.status != OrchestrationStatus.FAILED.value:
            return False
        reset = self.repository.reset_failed_for_resume(
            run.id, owner_id=owner_id, agent_id=agent_id
        )
        if reset is None:
            return False
        return self._ensure_job(reset) is not None

    def _run_to_dict(self, run, *, include_steps=False):
        timestamps = (
            "approved_at", "created_at", "updated_at", "started_at",
            "finished_at", "cancelled_at",
        )
        data = {
            "id": run.id,
            "kind": run.kind,
            "task": run.task,
            "agent_ids": list(run.agent_ids),
            "status": run.status,
            "revision": run.revision,
            "allow_high_tools": run.allow_high_tools,
            "current_job_id": run.current_job_id,
            "owner_id": run.owner_id,
            "agent_id": run.agent_id,
            "session_id": run.session_id,
            "result": run.result,
            "error_type": run.error_type,
            "total_steps": run.total_steps,
            "completed_steps": run.completed_steps,
            "max_turns": run.max_turns,
        }
        for name in timestamps:
            value = getattr(run, name)
            data[name] = value.isoformat() if value is not None else None
        if include_steps:
            data["steps"] = [
                self._step_to_dict(step)
                for step in self.repository.list_steps(run.id)
            ]
        return data

    @staticmethod
    def _step_to_dict(step):
        timestamps = ("created_at", "updated_at", "started_at", "finished_at")
        data = {
            "id": step.id,
            "position": step.position,
            "agent_id": step.agent_id,
            "turn": step.turn,
            "depends_on_step_id": step.depends_on_step_id,
            "status": step.status,
            "input_text": step.input_text,
            "result_text": step.result_text,
            "attempt_count": step.attempt_count,
            "max_attempts": step.max_attempts,
            "error_type": step.error_type,
        }
        for name in timestamps:
            value = getattr(step, name)
            data[name] = value.isoformat() if value is not None else None
        return data
