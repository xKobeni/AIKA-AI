import re


_INTERVAL_COMMAND = re.compile(
    r"^remind\s+every\s+(\d+)([mhd])\s+starting\s+(.+?)\s*\|\s*(.+)$",
    re.IGNORECASE,
)


def _print_reminders(reminders, output):
    if not reminders:
        output("No reminders found.")
        return
    for reminder in reminders:
        next_run = reminder.get("next_run_at") or "none"
        recurrence = reminder.get("recurrence") or "one-time"
        output(
            f"{reminder['id']} | {reminder['status']} | {next_run} | "
            f"{recurrence} | {reminder['message']}"
        )


def print_due_reminders(service, output=print):
    due = service.get_due_reminders(limit=100)
    if not due:
        return 0
    output("\nREMINDERS DUE")
    for item in due:
        output(
            f"- {item['message']}\n"
            f"  occurrence: {item['occurrence_id']} | "
            f"scheduled: {item['scheduled_for']}"
        )
    output("Use: ack reminder <occurrence_id>")
    return len(due)


def handle_reminder_command(service, user_input, output=print):
    text = user_input.strip()
    lowered = text.lower()

    if lowered == "list reminders":
        _print_reminders(service.get_reminders(limit=100), output)
        return True
    if lowered == "due reminders":
        if print_due_reminders(service, output) == 0:
            output("No reminders are due.")
        return True
    if lowered.startswith("ack reminder "):
        occurrence_id = text[len("ack reminder "):].strip()
        changed = service.acknowledge_reminder(occurrence_id)
        output("Reminder acknowledged." if changed else "Reminder not found.")
        return True
    if lowered.startswith("cancel reminder "):
        reminder_id = text[len("cancel reminder "):].strip()
        changed = service.cancel_reminder(reminder_id)
        output("Reminder cancelled." if changed else "Reminder not found or inactive.")
        return True
    if lowered.startswith("reschedule reminder "):
        rest = text[len("reschedule reminder "):].strip()
        reminder_id, separator, scheduled_for = rest.partition(" ")
        if not separator or not scheduled_for.strip():
            raise ValueError(
                "Usage: reschedule reminder <id> <ISO-8601 datetime>"
            )
        reminder = service.reschedule_reminder(
            reminder_id, scheduled_for.strip()
        )
        output(
            f"Reminder rescheduled for {reminder['next_run_at']}."
            if reminder else "Reminder not found or cancelled."
        )
        return True

    interval = _INTERVAL_COMMAND.fullmatch(text)
    if interval:
        amount = int(interval.group(1))
        unit = interval.group(2).lower()
        multiplier = {"m": 60, "h": 3600, "d": 86400}[unit]
        reminder, created = service.create_reminder(
            interval.group(4).strip(),
            interval.group(3).strip(),
            recurrence={"kind": "interval", "seconds": amount * multiplier},
        )
        label = "scheduled" if created else "already exists"
        output(f"Recurring reminder {label}: {reminder['id']}")
        return True

    if lowered.startswith("remind "):
        left, separator, message = text.partition("|")
        scheduled_for = left[len("remind "):].strip()
        if not separator or not scheduled_for or not message.strip():
            raise ValueError(
                "Usage: remind <ISO-8601 datetime> | <message>"
            )
        reminder, created = service.create_reminder(
            message.strip(), scheduled_for
        )
        label = "scheduled" if created else "already exists"
        output(f"Reminder {label}: {reminder['id']}")
        return True

    return False
