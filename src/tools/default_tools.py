from tools.app_launcher_tool import AppLauncherTool
from tools.calculator_tool import CalculatorTool
from tools.file_append_tool import FileAppendTool
from tools.file_delete_tool import FileDeleteTool
from tools.file_edit_tool import FileEditTool
from tools.file_grep_tool import FileGrepTool
from tools.file_mkdir_tool import FileMkdirTool
from tools.file_multi_edit_tool import FileMultiEditTool
from tools.file_read_range_tool import FileReadRangeTool
from tools.file_read_tool import FileReadTool
from tools.file_search_tool import FileSearchTool
from tools.file_write_tool import FileWriteTool
from tools.folder_tool import FolderTool
from tools.git_tool import GitTool
from tools.memory_search_tool import MemorySearchTool
from tools.shell_tool import ShellTool
from tools.system_info_tool import SystemInfoTool
from tools.test_runner_tool import TestRunnerTool
from tools.web_crawl_tool import WebCrawlTool
from tools.web_search_tool import WebSearchTool


def register_default_tools(tool_manager, memory_retrieval_service):
    tools = (
        CalculatorTool(),
        FileSearchTool(),
        FileReadTool(),
        FileWriteTool(),
        FileDeleteTool(),
        FileAppendTool(),
        FileEditTool(),
        FileGrepTool(),
        FileMkdirTool(),
        WebSearchTool(),
        WebCrawlTool(),
        MemorySearchTool(memory_retrieval_service),
        ShellTool(),
        AppLauncherTool(),
        FolderTool(),
        SystemInfoTool(),
        GitTool(),
        FileReadRangeTool(),
        FileMultiEditTool(),
        TestRunnerTool(),
    )
    for tool in tools:
        tool_manager.register_tool(tool)
    return tool_manager
