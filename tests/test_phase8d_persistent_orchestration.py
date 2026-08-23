from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock
import uuid

import pytest


def _run(**overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4().hex,
        "kind": "chain",
        "task": "Research and summarize",
        "agent_ids": ["researcher", "writer"],
        "status": "queued",
        "revision": 1,
        "allow_high_tools": False,
        "current_job_id": None,
        "owner_id": "owner-1",
        "agent_id": "aika",
        "session_id": "session-1",
        "idempotency_key": None,
        "result": None,
        "error_type": None,
        "total_steps": 2,
        "completed_steps": 0,
        "max_turns": 1,
        "approved_at": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
        "cancelled_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _step(position=0, **overrides):
    now = datetime.now(timezone.utc)
    values = {
        "id": uuid.uuid4().hex,
        "run_id": uuid.uuid4().hex,
        "position": position,
        "agent_id": "researcher",
        "turn": None,
        "depends_on_step_id": None,
        "status": "pending",
        "input_text": None,
        "result_text": None,
        "attempt_count": 0,
        "max_attempts": 2,
        "error_type": None,
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "finished_at": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_orchestration_models_and_migration_define_durable_runs_and_steps():
    from database.migrations import MIGRATIONS
    from database.models import OrchestrationRun, OrchestrationStep

    run_constraints = {
        constraint.name for constraint in OrchestrationRun.__table__.constraints
    }
    step_constraints = {
        constraint.name
        for constraint in OrchestrationStep.__table__.constraints
    }
    job_fk = next(
        iter(OrchestrationRun.__table__.c.current_job_id.foreign_keys)
    )
    run_fk = next(iter(OrchestrationStep.__table__.c.run_id.foreign_keys))
    dependency_fk = next(
        iter(OrchestrationStep.__table__.c.depends_on_step_id.foreign_keys)
    )
    migration = next(
        migration for migration in MIGRATIONS if migration.version == 5
    )

    assert "uq_orchestration_runs_idempotency_key" in run_constraints
    assert "uq_orchestration_steps_position" in step_constraints
    assert job_fk.target_fullname == "jobs.id"
    assert job_fk.ondelete == "SET NULL"
    assert run_fk.target_fullname == "orchestration_runs.id"
    assert run_fk.ondelete == "CASCADE"
    assert dependency_fk.target_fullname == "orchestration_steps.id"
    assert dependency_fk.ondelete == "SET NULL"
    assert migration.name == "persistent orchestration runs and steps"


class FakeJobRuntime:
    def __init__(self):
        self.definitions = {}
        self.jobs = {}
        self.cancelled = []
        self.approvals = []

    def register(self, definition):
        self.definitions[definition.name] = definition

    def enqueue(
        self,
        job_type,
        payload,
        *,
        owner_id=None,
        agent_id=None,
        session_id=None,
        idempotency_key=None,
    ):
        for job in self.jobs.values():
            if job["idempotency_key"] == idempotency_key:
                return job, False
        job = {
            "id": uuid.uuid4().hex,
            "type": job_type,
            "payload": payload,
            "status": "queued",
            "owner_id": owner_id,
            "agent_id": agent_id,
            "session_id": session_id,
            "idempotency_key": idempotency_key,
            "error_type": None,
        }
        self.jobs[job["id"]] = job
        return job, True

    def get_job(self, job_id):
        return self.jobs.get(job_id)

    def cancel_job(self, job_id):
        self.cancelled.append(job_id)
        if job_id in self.jobs:
            self.jobs[job_id]["status"] = "cancelled"
        return True

    def resolve_job_approval(self, job_id, approved):
        self.approvals.append((job_id, approved))
        if job_id not in self.jobs:
            return False
        self.jobs[job_id]["status"] = "queued" if approved else "cancelled"
        return True


class StateRepository:
    def __init__(self, run, steps):
        self.run = run
        self.steps = steps
        for step in self.steps:
            step.run_id = run.id

    def claim_job(self, run_id, revision, job_id):
        if run_id != self.run.id:
            return "missing", None
        if revision != self.run.revision:
            return "stale", self.run
        self.run.current_job_id = job_id
        return "claimed", self.run

    def mark_waiting_approval(self, run_id, revision, job_id):
        self.run.status = "waiting_approval"
        self.run.current_job_id = job_id
        return True

    def mark_approved(self, run_id, revision, job_id):
        self.run.approved_at = datetime.now(timezone.utc)
        self.run.status = "running"
        return True

    def prepare_resume(self, run_id, revision, job_id):
        for step in self.steps:
            if step.status == "running":
                if step.attempt_count >= step.max_attempts:
                    self.run.status = "failed"
                    self.run.error_type = "StepAttemptLimitExceeded"
                    return False
                step.status = "pending"
        self.run.status = "running"
        return True

    def get(self, run_id):
        return self.run if run_id == self.run.id else None

    def list_steps(self, run_id):
        return sorted(self.steps, key=lambda step: step.position)

    def next_step(self, run_id):
        completed = {step.id for step in self.steps if step.status == "completed"}
        for step in self.list_steps(run_id):
            if step.status == "pending" and (
                step.depends_on_step_id is None
                or step.depends_on_step_id in completed
            ):
                return step
        return None

    def start_step(self, run_id, step_id, input_text):
        step = next(item for item in self.steps if item.id == step_id)
        step.status = "running"
        step.input_text = input_text
        step.attempt_count += 1
        return step

    def complete_step(self, run_id, step_id, result_text):
        step = next(item for item in self.steps if item.id == step_id)
        step.status = "completed"
        step.result_text = result_text
        self.run.completed_steps += 1
        return True

    def fail_step(self, run_id, step_id, error_type):
        step = next(item for item in self.steps if item.id == step_id)
        step.status = "failed"
        step.error_type = error_type
        self.run.status = "failed"
        self.run.error_type = error_type
        return True

    def complete_run(self, run_id, result, skip_remaining=False):
        if skip_remaining:
            for step in self.steps:
                if step.status == "pending":
                    step.status = "skipped"
        self.run.status = "completed"
        self.run.result = result
        return True

    def cancel(self, run_id, **_filters):
        self.run.status = "cancelled"
        for step in self.steps:
            if step.status in {"pending", "running"}:
                step.status = "cancelled"
        return True, self.run.current_job_id

    def mark_failed_from_job(self, run_id, error_type):
        self.run.status = "failed"
        self.run.error_type = error_type
        return True


class FakeJobContext:
    def __init__(self, *, approved=False, cancel=False):
        self.job_id = uuid.uuid4().hex
        self.approval_granted = approved
        self.cancel = cancel
        self.progress = []

    def check_cancelled(self):
        if self.cancel:
            from jobs.types import JobCancelled

            raise JobCancelled("cancelled")

    def set_progress(self, progress, data=None):
        self.progress.append((progress, data))

    def require_approval(self, request):
        from jobs.types import JobAwaitingApproval

        raise JobAwaitingApproval(request)


def _registry():
    registry = Mock()
    registry.get.return_value = SimpleNamespace(is_active=True)
    return registry


def test_persistent_orchestrator_registers_non_retry_safe_job_and_chain_dependencies():
    from orchestration.runtime import (
        ORCHESTRATION_JOB_TYPE,
        PersistentOrchestrator,
    )

    runtime = FakeJobRuntime()
    repository = Mock()
    repository.list_nonterminal.return_value = []
    run = _run()
    repository.create.return_value = (run, True)
    repository.set_job.return_value = True
    orchestrator = PersistentOrchestrator(
        runtime, _registry(), Mock(), repository=repository
    )
    orchestrator.start()

    created, is_new = orchestrator.create_run(
        "chain", ["researcher", "writer"], "Do the work"
    )

    definition = runtime.definitions[ORCHESTRATION_JOB_TYPE]
    specs = repository.create.call_args.args[3]
    assert definition.retry_safe is False
    assert is_new is True
    assert created["id"] == run.id
    assert specs[0]["depends_on_position"] is None
    assert specs[1]["depends_on_position"] == 0
    assert len(runtime.jobs) == 1


def test_persistent_chain_commits_each_step_and_passes_previous_result():
    from orchestration.runtime import PersistentOrchestrator

    run = _run(status="queued")
    first = _step(0, run_id=run.id, agent_id="researcher")
    second = _step(
        1,
        run_id=run.id,
        agent_id="writer",
        depends_on_step_id=first.id,
    )
    repository = StateRepository(run, [first, second])
    calls = []

    def execute(agent_id, input_text, **_options):
        calls.append((agent_id, input_text))
        return "research result" if agent_id == "researcher" else "final report"

    orchestrator = PersistentOrchestrator(
        FakeJobRuntime(), _registry(), execute, repository=repository
    )
    context = FakeJobContext()
    result = orchestrator._execute_run(
        context, {"run_id": run.id, "revision": 1}
    )

    assert result["action"] == "completed"
    assert run.status == "completed"
    assert run.result == {"text": "final report"}
    assert "research result" in calls[1][1]
    assert [step.status for step in repository.steps] == [
        "completed", "completed"
    ]
    assert len(context.progress) == 2


def test_high_permission_orchestration_waits_for_explicit_job_approval():
    from jobs.types import JobAwaitingApproval
    from orchestration.runtime import PersistentOrchestrator

    run = _run(
        kind="delegate",
        agent_ids=["researcher"],
        total_steps=1,
        allow_high_tools=True,
    )
    step = _step(0, run_id=run.id)
    repository = StateRepository(run, [step])
    execute = Mock(return_value="done")
    orchestrator = PersistentOrchestrator(
        FakeJobRuntime(), _registry(), execute, repository=repository
    )

    with pytest.raises(JobAwaitingApproval):
        orchestrator._execute_run(
            FakeJobContext(), {"run_id": run.id, "revision": 1}
        )

    assert run.status == "waiting_approval"
    approved = FakeJobContext(approved=True)
    orchestrator._execute_run(
        approved, {"run_id": run.id, "revision": 1}
    )
    assert run.approved_at is not None
    execute.assert_called_once_with(
        "researcher", run.task, allow_high_tools=True
    )


def test_team_done_marker_completes_early_and_skips_remaining_steps():
    from orchestration.runtime import PersistentOrchestrator

    run = _run(
        kind="team",
        agent_ids=["researcher", "writer"],
        total_steps=4,
        max_turns=2,
    )
    steps = []
    previous = None
    for position in range(4):
        step = _step(
            position,
            run_id=run.id,
            agent_id=run.agent_ids[position % 2],
            turn=position // 2,
            depends_on_step_id=previous,
        )
        previous = step.id
        steps.append(step)
    repository = StateRepository(run, steps)
    orchestrator = PersistentOrchestrator(
        FakeJobRuntime(),
        _registry(),
        Mock(return_value="finished [TEAM_DONE]"),
        repository=repository,
    )

    result = orchestrator._execute_run(
        FakeJobContext(), {"run_id": run.id, "revision": 1}
    )

    assert result["team_done"] is True
    assert run.status == "completed"
    assert [step.status for step in steps] == [
        "completed", "skipped", "skipped", "skipped"
    ]


def test_job_cancellation_propagates_to_run_and_pending_steps():
    from jobs.types import JobCancelled
    from orchestration.runtime import PersistentOrchestrator

    run = _run()
    steps = [_step(0, run_id=run.id), _step(1, run_id=run.id)]
    repository = StateRepository(run, steps)
    orchestrator = PersistentOrchestrator(
        FakeJobRuntime(), _registry(), Mock(), repository=repository
    )

    with pytest.raises(JobCancelled):
        orchestrator._execute_run(
            FakeJobContext(cancel=True),
            {"run_id": run.id, "revision": 1},
        )

    assert run.status == "cancelled"
    assert all(step.status == "cancelled" for step in steps)


def test_create_run_validates_agents_limits_and_redacts_task_secrets():
    from orchestration.runtime import PersistentOrchestrator

    runtime = FakeJobRuntime()
    repository = Mock()
    repository.list_nonterminal.return_value = []
    repository.create.return_value = (_run(kind="delegate"), True)
    orchestrator = PersistentOrchestrator(
        runtime,
        _registry(),
        Mock(),
        repository=repository,
        max_agents=2,
        max_steps=2,
    )
    orchestrator.start()

    orchestrator.create_run(
        "delegate", ["researcher"], "Use token=secret-value"
    )
    stored_task = repository.create.call_args.args[1]
    assert "secret-value" not in stored_task
    with pytest.raises(ValueError, match="agent limit"):
        orchestrator.create_run("parallel", ["a", "b", "c"], "task")
    with pytest.raises(ValueError, match="exactly one"):
        orchestrator.create_run("delegate", ["a", "b"], "task")


def test_application_service_scopes_persistent_orchestration_operations():
    from application.service import AikaService

    brain = SimpleNamespace(
        current_agent_id="aika",
        current_session=SimpleNamespace(id="session-1"),
        tool_manager=None,
        llm=SimpleNamespace(model="test-model"),
        close=Mock(),
    )
    orchestrator = Mock()
    orchestrator.create_run.return_value = ({"id": "run-1"}, True)
    service = AikaService(
        brain=brain, persistent_orchestrator=orchestrator
    )

    service.create_orchestration("chain", ["a", "b"], "task")
    service.get_orchestration("run-1")
    service.get_orchestrations(limit=20)
    service.cancel_orchestration("run-1")

    orchestrator.create_run.assert_called_once_with(
        "chain",
        ["a", "b"],
        "task",
        agent_id="aika",
        session_id="session-1",
    )
    orchestrator.get_run.assert_called_once_with(
        "run-1", owner_id=None, agent_id="aika", include_steps=True
    )
    orchestrator.list_runs.assert_called_once_with(
        limit=20, owner_id=None, agent_id="aika"
    )
    orchestrator.cancel_run.assert_called_once_with(
        "run-1", owner_id=None, agent_id="aika"
    )


def test_service_background_step_serializes_brain_and_controls_high_tools():
    from application.service import AikaService

    policies = []
    tool_manager = Mock()
    tool_manager.set_high_permission_policy.side_effect = (
        lambda policy: policies.append(policy)
    )
    brain = SimpleNamespace(
        current_agent_id="aika",
        current_session=SimpleNamespace(id="session-1"),
        tool_manager=tool_manager,
        agent_loop=Mock(),
        llm=SimpleNamespace(model="test-model"),
        close=Mock(),
    )
    brain.agent_loop.run.return_value = "result"
    service = AikaService(brain=brain)

    result = service._execute_orchestration_step(
        "researcher", "task", allow_high_tools=True
    )

    assert result == "result"
    temporary_policy = policies[-2]
    assert temporary_policy("shell", {}) is True
    assert policies[-1] is None


def test_cancelled_foreground_request_does_not_start_after_background_wait():
    import threading

    from application.service import AikaService

    brain = SimpleNamespace(
        current_agent_id="aika",
        current_session=SimpleNamespace(id="session-1"),
        tool_manager=None,
        process_stream=Mock(return_value=iter(("unexpected",))),
        llm=SimpleNamespace(model="test-model"),
        close=Mock(),
    )
    service = AikaService(brain=brain)
    cancelled = threading.Event()
    cancelled.set()

    assert list(service._stream_brain_serialized("task", cancelled)) == []
    brain.process_stream.assert_not_called()


def test_durable_high_permission_policy_overrides_disabled_global_prompt():
    from config.settings import settings
    from tools.base_tool import BaseTool
    from tools.tool_category import ToolCategory
    from tools.tool_manager import ToolManager
    from tools.tool_permission import ToolPermission

    class HighTool(BaseTool):
        name = "phase8d_high"
        description = "test"
        category = ToolCategory.SYSTEM
        permission = ToolPermission.HIGH

        def execute(self, **kwargs):
            return {"success": True}

    manager = ToolManager()
    manager.register_tool(HighTool())
    original = settings.tool_call_confirm_high_permission
    settings.tool_call_confirm_high_permission = False
    try:
        manager.set_high_permission_policy(lambda _name, _params: False)
        denied = manager.execute_tool("phase8d_high")
        manager.set_high_permission_policy(lambda _name, _params: True)
        allowed = manager.execute_tool("phase8d_high")
    finally:
        manager.set_high_permission_policy(None)
        settings.tool_call_confirm_high_permission = original

    assert denied["success"] is False
    assert allowed["success"] is True


def test_cli_persistent_orchestration_commands_are_explicit_and_bounded():
    from orchestration.commands import handle_orchestration_command

    service = Mock()
    service.create_orchestration.return_value = (
        {
            "id": "run-1",
            "kind": "team",
            "status": "queued",
        },
        True,
    )
    service.get_orchestrations.return_value = []
    output = Mock()

    assert handle_orchestration_command(
        service,
        "start team --allow-high researcher,writer turns=3 | build report",
        output,
    )
    service.create_orchestration.assert_called_once_with(
        "team",
        ["researcher", "writer"],
        "build report",
        max_turns=3,
        allow_high_tools=True,
    )
    assert handle_orchestration_command(
        service, "list orchestrations", output
    )
    assert not handle_orchestration_command(service, "regular chat", output)
    assert not handle_orchestration_command(
        service, "start a normal conversation", output
    )
