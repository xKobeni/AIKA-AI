from brain.brain import AikaBrain

brain = AikaBrain()

print("AIKA Online")
print("Type 'exit' to quit | 'help' for commands")

while True:

    sid = brain.current_session.id[:4]
    user_input = input(f"\nYou [{sid}] > ")

    cmd = user_input.lower().strip()

    if cmd == "exit":
        break

    if cmd in ("help", "?"):
        print(
            "\nCommands:"
            "\n  new session         Start a fresh conversation"
            "\n  list sessions       Show all sessions"
            "\n  resume <id>         Continue a previous session"
            "\n  delete session <id> Remove a session"
            "\n  clear               Clear conversation history"
            "\n  !model [name]       Switch LLM model (e.g. !model llama3:8b)"
            "\n  !log [level]        Set log level (debug/info/warning/error)"
            "\n  !settings [cat]     View settings"
            "\n  !set KEY=value      Change a setting"
            "\n  !save               Save settings to .env"
            "\n  !reload             Reload settings from .env"
            "\n  !persona            View/change persona"
            "\n  help, ?             Show this help"
            "\n  exit                Quit"
        )
        continue

    try:
        response = brain.process(user_input)
    except Exception as e:
        print(f"\n[Error] {e}")
        continue

    print(f"\nAIKA > {response}")