import re


_SENSITIVE_KEYS = {
    "api_key", "apikey", "authorization", "content", "credential",
    "new_text", "old_text", "password", "secret", "token",
}
_SENSITIVE_KEY_PATTERN = re.compile(
    r"(?i)(?:^|[_-])(?:api[_-]?key|auth(?:orization)?|credential|password|passwd|"
    r"private[_-]?key|secret|token)(?:$|[_-])"
)
_SECRET_VALUE_PATTERN = re.compile(
    r"(?i)(bearer\s+|(?:api[_-]?key|password|secret|token)\s*[=:]\s*)"
    r"([^\s,;]+)"
)


def redact_sensitive(value, key=None):
    """Return a JSON-compatible shape with credential-like values removed."""
    if key and (
        key.lower() in _SENSITIVE_KEYS
        or _SENSITIVE_KEY_PATTERN.search(key)
    ):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {
            item_key: redact_sensitive(item_value, str(item_key))
            for item_key, item_value in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [redact_sensitive(item) for item in value]
    if isinstance(value, str):
        return _SECRET_VALUE_PATTERN.sub(r"\1[REDACTED]", value)
    return value
