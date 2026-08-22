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
