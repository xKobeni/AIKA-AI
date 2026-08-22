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

    service = AikaService()
    print("AIKA Online")
    print("Type 'exit' to quit | 'help' for commands")
    try:
        while True:
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
