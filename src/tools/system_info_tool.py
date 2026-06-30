import os
import platform
import logging

from tools.base_tool import BaseTool
from tools.tool_category import ToolCategory
from tools.tool_permission import ToolPermission
from config.settings import settings

logger = logging.getLogger(__name__)


class SystemInfoTool(BaseTool):

    description = "Returns information about the host system"
    category = ToolCategory.SYSTEM
    permission = ToolPermission.LOW

    @property
    def name(self):
        return "system_info"

    def get_schema(self):
        return {
            "name": self.name,
            "description": self.description,
            "parameters": {}
        }

    def execute(self):

        info = []

        try:
            uname = platform.uname()
            info.append(f"OS: {uname.system} {uname.release}")
            info.append(f"Version: {uname.version}")
            info.append(f"Machine: {uname.machine}")
            info.append(f"Processor: {uname.processor}")
        except Exception:
            info.append(f"OS: {platform.system()} {platform.release()}")

        info.append(f"Python: {platform.python_version()}")

        try:
            import psutil
            cpu = psutil.cpu_percent(interval=0.5)
            cpu_count = psutil.cpu_count(logical=True)
            info.append(f"CPU: {cpu}% used ({cpu_count} logical cores)")

            mem = psutil.virtual_memory()
            info.append(
                f"RAM: {mem.percent}% used "
                f"({mem.used // (1024 ** 3)} GB / {mem.total // (1024 ** 3)} GB)"
            )

            disk = psutil.disk_usage("/")
            info.append(
                f"Disk: {disk.percent}% used "
                f"({disk.used // (1024 ** 3)} GB / {disk.total // (1024 ** 3)} GB)"
            )

            boot = psutil.boot_time()
            from datetime import datetime
            uptime = datetime.now() - datetime.fromtimestamp(boot)
            days = uptime.days
            hours = uptime.seconds // 3600
            mins = (uptime.seconds % 3600) // 60
            info.append(f"Uptime: {days}d {hours}h {mins}m")

        except ImportError:
            info.append(
                "CPU cores: {} ({})".format(
                    platform.machine(),
                    os.cpu_count()
                )
            )

        return {
            "success": True,
            "info": info,
            "text": "\n".join(info)
        }
