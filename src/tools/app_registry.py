import os
import time
import json
import logging
import subprocess
import sys

logger = logging.getLogger(__name__)

CACHE_DIR = os.path.join(
    os.environ.get("APPDATA", os.path.expandvars(r"%LOCALAPPDATA%")),
    "aika_ai"
)
CACHE_FILE = os.path.join(CACHE_DIR, "app_cache.json")
CACHE_TTL = 300


def scan_registry_apps():
    """Scan Windows Registry App Paths and Uninstall keys for installed apps."""
    if sys.platform != "win32":
        return {}
    import winreg

    apps = {}

    registry_paths = [
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths"),
        (winreg.HKEY_CURRENT_USER,
         r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"),
    ]

    for hive, sub_key in registry_paths:
        try:
            key = winreg.OpenKey(hive, sub_key)
        except (FileNotFoundError, PermissionError):
            continue
        try:
            count, _, _ = winreg.QueryInfoKey(key)
            for i in range(count):
                try:
                    app_name = winreg.EnumKey(key, i)
                    app_key = winreg.OpenKey(key, app_name)
                    try:
                        exe_path, _ = winreg.QueryValueEx(app_key, "")
                        expanded = os.path.expandvars(exe_path)
                        if os.path.isfile(expanded):
                            name_key = app_name.lower().replace(".exe", "")
                            apps[name_key] = {
                                "name": name_key,
                                "path": expanded,
                                "source": "registry"
                            }
                    except FileNotFoundError:
                        pass
                    finally:
                        winreg.CloseKey(app_key)
                except OSError:
                    continue
        finally:
            winreg.CloseKey(key)

    return apps


def scan_start_menu_apps():
    """Scan Start Menu .lnk shortcuts for installed apps."""
    if sys.platform != "win32":
        return {}
    try:
        import pythoncom
        import win32com.client
        pythoncom.CoInitialize()
    except ImportError:
        logger.debug("pywin32 not available, skipping Start Menu scan")
        return {}

    apps = {}
    start_menu_paths = []

    app_data = os.environ.get("APPDATA")
    program_data = os.environ.get("PROGRAMDATA")
    if app_data:
        start_menu_paths.append(
            os.path.join(app_data, "Microsoft", "Windows", "Start Menu", "Programs")
        )
    if program_data:
        start_menu_paths.append(
            os.path.join(program_data, "Microsoft", "Windows", "Start Menu", "Programs")
        )

    try:
        shell = win32com.client.Dispatch("WScript.Shell")
    except Exception:
        logger.debug("Failed to create WScript.Shell COM object")
        return apps

    for base_path in start_menu_paths:
        if not os.path.isdir(base_path):
            continue
        for root, dirs, files in os.walk(base_path):
            for f in files:
                if not f.lower().endswith(".lnk"):
                    continue
                lnk_path = os.path.join(root, f)
                try:
                    shortcut = shell.CreateShortCut(lnk_path)
                    target = shortcut.Targetpath
                    if target and os.path.isfile(target):
                        name_key = os.path.splitext(f)[0].lower()
                        if name_key not in apps:
                            apps[name_key] = {
                                "name": name_key,
                                "path": target,
                                "source": "start_menu"
                            }
                except Exception:
                    continue

    return apps


def scan_uwp_apps():
    """Scan Microsoft Store (UWP) apps using Get-StartApps."""
    if sys.platform != "win32":
        return {}
    try:
        result = subprocess.run(
            ["powershell.exe", "-NoProfile", "-Command",
             "Get-StartApps | ForEach-Object { $_.Name + '|' + $_.AppID }"],
            capture_output=True, text=True, timeout=15
        )
    except Exception:
        logger.debug("UWP scan failed")
        return {}

    apps = {}
    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if "|" not in line:
            continue
        name, aumid = line.split("|", 1)
        name_key = name.lower().strip()
        if name_key not in apps:
            apps[name_key] = {
                "name": name.strip(),
                "aumid": aumid.strip(),
                "source": "uwp"
            }

    return apps


class AppRegistry:

    def __init__(self, enable_uwp=True):
        self._cache = None
        self._cache_time = 0
        self._cache_ttl = CACHE_TTL
        self._enable_uwp = enable_uwp

    def _load_file_cache(self):
        try:
            if os.path.isfile(CACHE_FILE):
                with open(CACHE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if time.time() - data.get("timestamp", 0) < self._cache_ttl:
                    return data.get("apps", {})
        except Exception:
            pass
        return None

    def _save_file_cache(self, apps):
        try:
            os.makedirs(CACHE_DIR, exist_ok=True)
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({"timestamp": time.time(), "apps": apps}, f, indent=2)
        except Exception:
            pass

    def get_all_apps(self):
        if self._cache and (time.time() - self._cache_time) < self._cache_ttl:
            return self._cache

        file_cache = self._load_file_cache()
        if file_cache is not None:
            self._cache = file_cache
            self._cache_time = time.time()
            return self._cache

        t0 = time.time()
        apps = {}
        apps.update(scan_registry_apps())
        apps.update(scan_start_menu_apps())
        if self._enable_uwp:
            apps.update(scan_uwp_apps())
        logger.debug("System app scan: %d apps in %.2fs", len(apps), time.time() - t0)

        self._cache = apps
        self._cache_time = time.time()
        self._save_file_cache(apps)
        return apps

    def find_app(self, name):
        apps = self.get_all_apps()
        name_lower = name.lower().strip()

        if name_lower in apps:
            return apps[name_lower]

        for key, info in apps.items():
            if name_lower in key or key in name_lower:
                return info

        return None
