def _print_help():
    print(
        "\nCommands:"
        "\n  new session         Start a fresh conversation"
        "\n  list sessions       Show all sessions"
        "\n  resume <id>         Continue a previous session"
        "\n  delete session <id> Remove a session"
        "\n  clear               Clear conversation history"
        "\n  list agents         Show all registered agents"
        "\n  use <agent_id>      Switch to a different agent"
        "\n  create agent <id> <name>  Create a new agent"
        "\n  remind <ISO> | <message>  Schedule a one-time reminder"
        "\n  remind every <N>[m|h|d] starting <ISO> | <message>"
        "\n  list reminders       Show scheduled reminders"
        "\n  due reminders        Show unacknowledged reminders"
        "\n  ack reminder <id>    Acknowledge a due occurrence"
        "\n  cancel reminder <id> Cancel an active reminder"
        "\n  reschedule reminder <id> <ISO>"
        "\n  start delegate <agent> | <task>  Start durable delegation"
        "\n  start chain <a,b> | <task>       Start durable chain"
        "\n  start parallel <a,b> | <task>    Start durable independent steps"
        "\n  start team <a,b> [turns=N] | <task>"
        "\n  list orchestrations              Show durable runs"
        "\n  show orchestration <id>          Show run and step details"
        "\n  cancel orchestration <id>        Cancel unfinished work"
        "\n  resume orchestration <id>        Resume approved/failed work"
        "\n  approve orchestration <id>       Approve a waiting run"
        "\n  reject orchestration <id>        Reject a waiting run"
        "\n  !model [name]       Switch LLM model"
        "\n  !log [level]        Set log level"
        "\n  !settings [cat]     View settings"
        "\n  !set KEY=value      Change a setting"
        "\n  !save               Save settings to .env"
        "\n  !reload             Reload settings from .env"
        "\n  !persona            View/change persona"
        "\n  help, ?             Show this help"
        "\n  exit                Quit"
    )


def main():
    from application.events import AikaEventType
    from application.service import AikaService
    from orchestration.commands import handle_orchestration_command
    from reminders.commands import handle_reminder_command, print_due_reminders

    service = AikaService(
        enable_jobs=True,
        enable_reminders=True,
        enable_orchestration=True,
    )

    def print_live_reminder(item):
        print(
            f"\n\nAIKA REMINDER > {item['message']}\n"
            f"Occurrence: {item['occurrence_id']}\n"
            "Use: ack reminder <occurrence_id>"
        )

    service.set_reminder_handler(print_live_reminder)

    def print_orchestration_update(run):
        print(
            f"\n\nAIKA ORCHESTRATION > {run['id']} is {run['status']}\n"
            f"Progress: {run['completed_steps']}/{run['total_steps']} steps"
        )

    service.set_orchestration_handler(print_orchestration_update)
    print("AIKA Online")
    print("Type 'exit' to quit | 'help' for commands")
    try:
        while True:
            try:
                print_due_reminders(service)
            except Exception as exc:
                print(f"\n[Reminder error] {type(exc).__name__}")
            agent_label = service.current_agent_id
            sid = service.current_session_id[:4]
            user_input = input(f"\nYou [{agent_label}:{sid}] > ")
            cmd = user_input.lower().strip()

            if cmd == "exit":
                break
            if cmd in ("help", "?"):
                _print_help()
                continue

            try:
                if handle_orchestration_command(service, user_input):
                    continue
                if handle_reminder_command(service, user_input):
                    continue
                print("\nAIKA > ", end="", flush=True)
                for event in service.stream(user_input):
                    if event.type == AikaEventType.TEXT_DELTA:
                        print(event.data.get("text", ""), end="", flush=True)
                    elif event.type == AikaEventType.APPROVAL_REQUIRED:
                        print("\n\n" + "=" * 50)
                        print("HIGH PERMISSION TOOL REQUEST")
                        print(f"Tool: {event.data['tool_name']}")
                        print(f"Parameters: {event.data['parameters']}")
                        print("=" * 50)
                        answer = input("Execute? [y/N]: ").strip().lower()
                        service.resolve_confirmation(
                            event.data["confirmation_id"],
                            answer in ("y", "yes"),
                        )
                    elif event.type == AikaEventType.ERROR:
                        if not event.data.get("already_reported", False):
                            print(
                                f"\n[Error] {event.data.get('error', 'Operation failed')}",
                                end="",
                            )
                    elif event.type == AikaEventType.CANCELLED:
                        print("\n[Interrupted]", end="")
                print()
            except KeyboardInterrupt:
                service.cancel_active()
                print("\n[Interrupted]")
            except Exception as exc:
                print(f"\n[Error] {exc}")
    finally:
        service.close(wait=True)


if __name__ == "__main__":
    main()
