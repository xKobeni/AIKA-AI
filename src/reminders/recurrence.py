import math
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def get_timezone(timezone_name):
    if not isinstance(timezone_name, str) or not timezone_name.strip():
        raise ValueError("timezone must be a non-empty IANA timezone name")
    timezone_name = timezone_name.strip()
    if len(timezone_name) > 64:
        raise ValueError("timezone exceeds 64 characters")
    # UTC is part of the standard library and should remain available even on
    # platforms (notably Windows) that do not provide an IANA timezone database.
    if timezone_name == "UTC":
        return timezone_name, timezone.utc
    try:
        return timezone_name, ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"unknown timezone: {timezone_name}") from exc


def _normalize_wall_datetime(value, zone):
    aware = value.replace(tzinfo=zone)
    round_trip = aware.astimezone(timezone.utc).astimezone(zone)
    if round_trip.replace(tzinfo=None) != value:
        aware = round_trip
    return aware


def normalize_schedule_time(value, timezone_name):
    _, zone = get_timezone(timezone_name)
    if isinstance(value, str):
        text = value.strip()
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            value = datetime.fromisoformat(text)
        except ValueError as exc:
            raise ValueError("scheduled_for must be an ISO-8601 datetime") from exc
    if not isinstance(value, datetime):
        raise ValueError("scheduled_for must be a datetime or ISO-8601 string")
    if value.tzinfo is None or value.utcoffset() is None:
        value = _normalize_wall_datetime(value, zone)
    return value.astimezone(timezone.utc)


def _normalize_clock(value):
    if not isinstance(value, str):
        raise ValueError("recurrence time must use HH:MM or HH:MM:SS")
    try:
        parsed = time.fromisoformat(value.strip())
    except ValueError as exc:
        raise ValueError("recurrence time must use HH:MM or HH:MM:SS") from exc
    if parsed.tzinfo is not None:
        raise ValueError("recurrence time must not include a timezone offset")
    return parsed.replace(microsecond=0).isoformat(timespec="seconds")


def normalize_recurrence(value, *, min_interval_seconds=60):
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("recurrence must be a JSON object")
    kind = str(value.get("kind", "")).strip().lower()
    if kind == "interval":
        seconds = value.get("seconds")
        if isinstance(seconds, bool) or not isinstance(seconds, int):
            raise ValueError("interval recurrence requires integer seconds")
        if seconds < int(min_interval_seconds):
            raise ValueError(
                f"interval recurrence must be at least {int(min_interval_seconds)} seconds"
            )
        return {"kind": "interval", "seconds": seconds}
    if kind == "daily":
        return {"kind": "daily", "time": _normalize_clock(value.get("time"))}
    if kind == "weekly":
        weekday = value.get("weekday")
        if isinstance(weekday, bool) or not isinstance(weekday, int):
            raise ValueError("weekly recurrence requires weekday 0 through 6")
        if not 0 <= weekday <= 6:
            raise ValueError("weekly recurrence requires weekday 0 through 6")
        return {
            "kind": "weekly",
            "weekday": weekday,
            "time": _normalize_clock(value.get("time")),
        }
    raise ValueError("recurrence kind must be interval, daily, or weekly")


def _local_candidate(local_date, clock, zone):
    naive = datetime.combine(local_date, time.fromisoformat(clock))
    return _normalize_wall_datetime(naive, zone)


def next_occurrence(scheduled_for, recurrence, timezone_name, *, now=None):
    recurrence = normalize_recurrence(recurrence, min_interval_seconds=1)
    if recurrence is None:
        return None
    scheduled_for = normalize_schedule_time(scheduled_for, timezone_name)
    now = now or datetime.now(timezone.utc)
    if now.tzinfo is None or now.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    reference = max(scheduled_for, now.astimezone(timezone.utc))

    if recurrence["kind"] == "interval":
        seconds = recurrence["seconds"]
        elapsed = max(0.0, (reference - scheduled_for).total_seconds())
        steps = math.floor(elapsed / seconds) + 1
        return scheduled_for + timedelta(seconds=steps * seconds)

    _, zone = get_timezone(timezone_name)
    local_reference = reference.astimezone(zone)
    if recurrence["kind"] == "daily":
        candidate = _local_candidate(
            local_reference.date(), recurrence["time"], zone
        )
        if candidate <= local_reference:
            candidate = _local_candidate(
                local_reference.date() + timedelta(days=1),
                recurrence["time"],
                zone,
            )
        return candidate.astimezone(timezone.utc)

    days_ahead = (recurrence["weekday"] - local_reference.weekday()) % 7
    candidate = _local_candidate(
        local_reference.date() + timedelta(days=days_ahead),
        recurrence["time"],
        zone,
    )
    if candidate <= local_reference:
        candidate = _local_candidate(
            candidate.date() + timedelta(days=7),
            recurrence["time"],
            zone,
        )
    return candidate.astimezone(timezone.utc)
