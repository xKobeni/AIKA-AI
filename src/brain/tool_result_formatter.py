import logging

logger = logging.getLogger(__name__)


class ToolResultFormatter:

    MAX_RESULT_CHARS = 3000
    MAX_LINES = 80

    def format_for_context(self, tool_name, tool_request, result):
        if not isinstance(result, dict):
            return self._format_raw(str(result), tool_name)

        if not result.get("success", True):
            error = result.get("error", "Unknown error")
            return f"[Tool Result: {tool_name}] ERROR: {error} [End Result]"

        content = self._extract_content(tool_name, result)
        return self._format_raw(content, tool_name)

    def _extract_content(self, tool_name, result):
        extractors = {
            "calculator": lambda r: r.get("result", str(r)),
            "date_time": lambda r: r.get("text", str(r)),
            "capabilities": lambda r: r.get("text", str(r)),
            "file_read": lambda r: r.get("content", str(r)),
            "file_read_range": lambda r: r.get("content", str(r)),
            "file_search": lambda r: "\n".join(r.get("file_paths", [])) or "No files found",
            "file_write": lambda r: f"Written to {r.get('file_path', '?')}",
            "file_edit": lambda r: f"Edited {r.get('file_path', '?')} ({r.get('replacements_made', 0)} replacements)",
            "file_multi_edit": lambda r: self._format_multi_edit_results(r),
            "file_delete": lambda r: r.get("message", f"Deleted {r.get('file_path', '?')}"),
            "file_append": lambda r: f"Appended to {r.get('file_path', '?')}",
            "file_mkdir": lambda r: r.get("message", f"Created {r.get('dir_path', '?')}"),
            "file_grep": lambda r: self._format_grep_results(r),
            "web_search": lambda r: self._format_web_results(r),
            "web_crawl": lambda r: r.get("content", str(r))[:2000],
            "memory_search": lambda r: "\n".join(r.get("memories", [])) or "No memories found",
            "shell": lambda r: self._format_shell_result(r),
            "app_launcher": lambda r: r.get("message", str(r)),
            "folder": lambda r: self._format_folder_result(r),
            "system_info": lambda r: r.get("text", str(r)),
            "git": lambda r: r.get("output", str(r)),
            "test_runner": lambda r: r.get("output", str(r))[:3000],
        }

        extractor = extractors.get(tool_name, lambda r: str(r))
        return extractor(result)

    def _format_grep_results(self, result):
        matches = result.get("matches", [])
        if not matches:
            return "No matches found"
        lines = []
        for m in matches[:20]:
            lines.append(f"  {m.get('file', '?')}:{m.get('line_number', '?')}: {m.get('line', '')}")
        return "\n".join(lines)

    def _format_multi_edit_results(self, result):
        results = result.get("results", [])
        if not results:
            return "No edits performed"
        lines = []
        for r in results:
            status = "ok" if r.get("success") else f"FAILED: {r.get('error', '?')}"
            lines.append(f"  {r.get('file_path', '?')}: {status}")
        return "\n".join(lines)

    def _format_web_results(self, result):
        results = result.get("results", [])
        if not results:
            return "No search results"
        lines = []
        for r in results[:5]:
            title = r.get("title", "")
            url = r.get("href", r.get("url", ""))
            snippet = r.get("body", r.get("snippet", ""))
            lines.append(f"- {title}\n  URL: {url}\n  {snippet}")
        return "\n\n".join(lines)

    def _format_shell_result(self, result):
        parts = []
        if result.get("stdout"):
            parts.append(result["stdout"][:1500])
        if result.get("stderr"):
            parts.append(f"STDERR: {result['stderr'][:500]}")
        if result.get("exit_code", 0) != 0:
            parts.append(f"Exit code: {result['exit_code']}")
        return "\n".join(parts) if parts else "Command completed"

    def _format_folder_result(self, result):
        folders = result.get("folders", [])
        files = result.get("files", [])
        lines = []
        for f in folders[:20]:
            lines.append(f"  {f}")
        for f in files[:30]:
            lines.append(f"  {f}")
        return "\n".join(lines) if lines else "Empty directory"

    def _format_raw(self, content, tool_name):
        content = str(content)
        if len(content) > self.MAX_RESULT_CHARS:
            content = content[:self.MAX_RESULT_CHARS] + "\n...[truncated]"
        lines = content.split("\n")
        if len(lines) > self.MAX_LINES:
            content = "\n".join(lines[:self.MAX_LINES]) + "\n...[truncated]"
        return f"[Tool Result: {tool_name}] {content} [End Result]"
