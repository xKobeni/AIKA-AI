import fnmatch
import os
from pathlib import Path

from config.settings import settings


OUTSIDE_WORKSPACE_ERROR = "Access denied: path is outside workspace"
DEFAULT_SCAN_EXCLUDED_DIRS = frozenset({
    ".git", ".hg", ".svn", ".venv", "venv", "node_modules",
    "__pycache__", ".pytest_cache", ".mypy_cache", ".ruff_cache",
    "dist", "build",
})


def resolve_known_user_folder(name):
    """Resolve a narrow set of OS-known user folders without guessing names."""
    normalized = str(name).strip().lower()
    aliases = {
        "desktop": ("Desktop", "Desktop"),
        "download": (
            "{374DE290-123F-4565-9164-39C4925E467B}",
            "Downloads",
        ),
        "downloads": (
            "{374DE290-123F-4565-9164-39C4925E467B}",
            "Downloads",
        ),
    }
    if normalized not in aliases:
        return None
    registry_name, folder_name = aliases[normalized]

    candidates = []
    if os.name == "nt":
        try:
            import winreg

            key_path = (
                r"Software\Microsoft\Windows\CurrentVersion\Explorer"
                r"\User Shell Folders"
            )
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
                value, _ = winreg.QueryValueEx(key, registry_name)
            candidates.append(Path(os.path.expandvars(value)))
        except (ImportError, OSError):
            pass

    one_drive = os.getenv("OneDrive")
    user_profile = os.getenv("USERPROFILE")
    if normalized == "desktop" and one_drive:
        candidates.append(Path(one_drive) / folder_name)
    if user_profile:
        candidates.append(Path(user_profile) / folder_name)
    candidates.append(Path.home() / folder_name)

    for candidate in candidates:
        if candidate.is_dir():
            return candidate.resolve()
    return candidates[0].resolve() if candidates else None


def resolve_user_scoped_path(default_root, requested_path):
    """Resolve workspace paths plus the explicit desktop:// user location."""
    requested = str(requested_path or ".").strip()
    normalized = requested.replace("\\", "/")
    lowered = normalized.lower()
    if lowered == "desktop" or lowered.startswith("desktop://"):
        root = resolve_known_user_folder("desktop")
        if root is None:
            return Path(default_root).resolve(), None
        relative = "" if lowered == "desktop" else normalized[len("desktop://"):]
        return resolve_workspace_path(root, relative or ".")
    return resolve_workspace_path(default_root, requested)


def resolve_workspace_path(root_path, requested_path):
    """Resolve a requested path and prove it remains inside the workspace."""
    root = Path(root_path).resolve()
    path = (root / requested_path).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return root, None
    return root, path


def is_protected_path(path, root=None):
    """Match configured protected names against a normalized relative path."""
    candidate = Path(path)
    if root is not None:
        try:
            candidate = candidate.relative_to(Path(root))
        except ValueError:
            pass

    normalized = candidate.as_posix().lower()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    parts = [part.lower() for part in candidate.parts if part not in (".", "..")]

    for pattern in settings.protected_paths:
        pattern = pattern.strip().replace("\\", "/").lower()
        if pattern.startswith("./"):
            pattern = pattern[2:]
        if not pattern:
            continue
        if fnmatch.fnmatch(normalized, pattern):
            return True
        if "/" not in pattern and any(
            fnmatch.fnmatch(part, pattern) for part in parts
        ):
            return True
    return False


def iter_scannable_files(root, start=None, recursive=True, max_files=10000):
    """Yield contained, non-protected files while pruning expensive caches."""
    root = Path(root).resolve()
    start = Path(start or root).resolve()
    scanned = 0

    for current, dirnames, filenames in os.walk(start, followlinks=False):
        current_path = Path(current)
        allowed_dirs = []
        for dirname in dirnames:
            candidate = current_path / dirname
            _, safe_dir = resolve_workspace_path(root, candidate)
            if safe_dir is None:
                continue
            if dirname.lower() in DEFAULT_SCAN_EXCLUDED_DIRS:
                continue
            if is_protected_path(safe_dir, root):
                continue
            allowed_dirs.append(dirname)
        dirnames[:] = allowed_dirs if recursive else []

        for filename in filenames:
            candidate = current_path / filename
            _, safe_file = resolve_workspace_path(root, candidate)
            if safe_file is None or is_protected_path(safe_file, root):
                continue
            if not safe_file.is_file():
                continue
            yield safe_file
            scanned += 1
            if scanned >= max(1, max_files):
                return
