def _format_run(run, *, detailed=False):
    progress = f"{run['completed_steps']}/{run['total_steps']}"
    lines = [
        f"{run['id']} | {run['kind']} | {run['status']} | steps {progress}",
        f"  agents: {', '.join(run['agent_ids'])}",
        f"  task: {run['task'][:160]}",
    ]
    if run.get("error_type"):
        lines.append(f"  error: {run['error_type']}")
    if run.get("current_job_id"):
        lines.append(f"  job: {run['current_job_id']}")
    if detailed:
        for step in run.get("steps", []):
            line = (
                f"  step {step['position'] + 1}: {step['agent_id']} | "
                f"{step['status']} | attempts "
                f"{step['attempt_count']}/{step['max_attempts']}"
            )
            lines.append(line)
            if step.get("error_type"):
                lines.append(f"    error: {step['error_type']}")
        if run.get("result") is not None:
            lines.append(f"  result: {run['result']}")
    return "\n".join(lines)


def _parse_start(command):
    left, separator, task = command.partition("|")
    if not separator or not task.strip():
        raise ValueError(
            "Usage: start <delegate|chain|parallel|team> "
            "[--allow-high] <agents> [turns=N] | <task>"
        )
    tokens = left.strip().split()
    if len(tokens) < 3 or tokens[0].lower() != "start":
        raise ValueError("Invalid persistent orchestration command")
    kind = tokens[1].lower()
    options = tokens[2:]
    allow_high = False
    max_turns = 1
    agent_token = None
    for token in options:
        lowered = token.lower()
        if lowered == "--allow-high":
            allow_high = True
        elif lowered.startswith("turns="):
            try:
                max_turns = int(token.split("=", 1)[1])
            except ValueError as exc:
                raise ValueError("turns must be an integer") from exc
        elif agent_token is None:
            agent_token = token
        else:
            raise ValueError("Unexpected orchestration start option")
    if not agent_token:
        raise ValueError("At least one agent is required")
    agent_ids = [item.strip() for item in agent_token.split(",") if item.strip()]
    return kind, agent_ids, task.strip(), max_turns, allow_high


def handle_orchestration_command(service, user_input, output=print):
    command = user_input.strip()
    lowered = command.lower()

    if any(
        lowered.startswith(f"start {kind} ")
        for kind in ("delegate", "chain", "parallel", "team")
    ):
        try:
            kind, agents, task, turns, allow_high = _parse_start(command)
            run, created = service.create_orchestration(
                kind,
                agents,
                task,
                max_turns=turns,
                allow_high_tools=allow_high,
            )
            verb = "created" if created else "already exists"
            output(
                f"Persistent orchestration {verb}: {run['id']} "
                f"({run['kind']}, {run['status']})"
            )
            if allow_high:
                output(
                    "This run will pause for explicit approval before "
                    "high-permission tools are allowed."
                )
        except ValueError as exc:
            output(f"Orchestration error: {exc}")
        return True

    if lowered == "list orchestrations":
        runs = service.get_orchestrations(limit=50)
        if not runs:
            output("No persistent orchestrations.")
        else:
            output("\n\n".join(_format_run(run) for run in runs))
        return True

    prefixes = {
        "show orchestration ": "show",
        "cancel orchestration ": "cancel",
        "resume orchestration ": "resume",
        "approve orchestration ": "approve",
        "reject orchestration ": "reject",
    }
    for prefix, action in prefixes.items():
        if lowered.startswith(prefix):
            run_id = command[len(prefix):].strip()
            if not run_id or " " in run_id:
                output(f"Usage: {prefix}<run_id>")
                return True
            if action == "show":
                run = service.get_orchestration(run_id)
                output(
                    _format_run(run, detailed=True)
                    if run is not None else "Orchestration not found."
                )
            elif action == "cancel":
                output(
                    "Cancellation requested."
                    if service.cancel_orchestration(run_id)
                    else "Orchestration could not be cancelled."
                )
            elif action == "resume":
                output(
                    "Orchestration resumed."
                    if service.resume_orchestration(run_id)
                    else "Orchestration could not be resumed."
                )
            else:
                approved = action == "approve"
                output(
                    "Orchestration approval resolved."
                    if service.resolve_orchestration_approval(
                        run_id, approved
                    )
                    else "Orchestration is not waiting for approval."
                )
            return True
    return False
