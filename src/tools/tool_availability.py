"""Shared runtime checks for registered AIKA tools."""

from config.settings import settings


SETTING_BY_TOOL = {
    "app_launcher": "app_launcher_enabled",
    "shell": "shell_enabled",
    "file_write": "file_write_enabled",
    "file_append": "file_write_enabled",
    "file_edit": "file_write_enabled",
    "file_mkdir": "file_write_enabled",
    "file_multi_edit": "file_write_enabled",
    "file_delete": "file_delete_enabled",
}


def is_tool_runtime_enabled(tool_name):
    setting_name = SETTING_BY_TOOL.get(str(tool_name or ""))
    if setting_name is None:
        return True
    return bool(getattr(settings, setting_name, True))
