from pathlib import Path
from unittest.mock import Mock, patch


def _shell_settings(mock_settings, root):
    mock_settings.shell_enabled = True
    mock_settings.shell_unsafe_enabled = False
    mock_settings.shell_timeout = 30
    mock_settings.shell_blocked_keywords = []
    mock_settings.file_search_root_path = str(root)
    mock_settings.shell_allowed_workdirs = ["."]


def test_shell_safe_mode_uses_argument_array_and_shell_false(tmp_path):
    from tools.shell_tool import ShellTool

    with patch("tools.shell_tool.settings") as mock_settings, patch(
        "tools.shell_tool.subprocess.run"
    ) as run:
        _shell_settings(mock_settings, tmp_path)
        run.return_value = Mock(returncode=0, stdout="ok", stderr="")

        result = ShellTool().execute("program --flag value")

    assert result["success"] is True
    run.assert_called_once_with(
        ["program", "--flag", "value"], shell=False,
        capture_output=True, text=True, timeout=30, cwd=str(tmp_path.resolve())
    )


def test_shell_safe_mode_rejects_operators(tmp_path):
    from tools.shell_tool import ShellTool

    with patch("tools.shell_tool.settings") as mock_settings:
        _shell_settings(mock_settings, tmp_path)
        result = ShellTool().execute("first | second")

    assert result["success"] is False
    assert "operators" in result["error"]


def test_unsafe_shell_requires_explicit_setting(tmp_path):
    from tools.shell_tool import ShellTool

    with patch("tools.shell_tool.settings") as mock_settings:
        _shell_settings(mock_settings, tmp_path)
        result = ShellTool().execute("echo one | echo two", unsafe=True)

    assert result == {"success": False, "error": "Unsafe shell mode is disabled"}


def test_unsafe_shell_enabled_is_explicit_and_auditable(tmp_path):
    from tools.shell_tool import ShellTool

    with patch("tools.shell_tool.settings") as mock_settings, patch(
        "tools.shell_tool.subprocess.run"
    ) as run:
        _shell_settings(mock_settings, tmp_path)
        mock_settings.shell_unsafe_enabled = True
        run.return_value = Mock(returncode=0, stdout="", stderr="")
        result = ShellTool().execute("echo one | echo two", unsafe=True)

    assert result["success"] is True
    assert run.call_args.kwargs["shell"] is True


def test_shell_workdir_must_remain_in_allowed_workspace(tmp_path):
    from tools.shell_tool import ShellTool

    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    with patch("tools.shell_tool.settings") as mock_settings:
        _shell_settings(mock_settings, tmp_path)
        result = ShellTool().execute("echo no", workdir=str(outside))

    assert result["success"] is False
    assert "outside workspace" in result["error"]


def test_crawler_rejects_private_and_non_http_urls():
    from tools.url_security import URLSecurityError, validate_public_url

    private_resolver = Mock(return_value=[
        (None, None, None, None, ("127.0.0.1", 80))
    ])
    try:
        validate_public_url("http://example.test", resolver=private_resolver)
        assert False, "private address should have been rejected"
    except URLSecurityError as error:
        assert "Private" in str(error)

    try:
        validate_public_url("file:///etc/passwd")
        assert False, "file URL should have been rejected"
    except URLSecurityError as error:
        assert "http and https" in str(error)


def test_crawler_allows_public_dns_results():
    from tools.url_security import validate_public_url

    resolver = Mock(return_value=[
        (None, None, None, None, ("93.184.216.34", 443))
    ])
    assert validate_public_url(
        "https://example.com/path", resolver=resolver
    ) == "https://example.com/path"


def test_crawler_validates_every_redirect_target():
    from tools.url_security import URLSecurityError, fetch_public_url

    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.status_code = 302
    response.headers = {"location": "http://127.0.0.1/admin"}
    client = Mock()
    client.stream.return_value = response
    resolver = Mock(return_value=[
        (None, None, None, None, ("93.184.216.34", 80))
    ])

    try:
        fetch_public_url(
            "http://example.com", client=client, resolver=resolver
        )
        assert False, "private redirect should have been rejected"
    except URLSecurityError as error:
        assert "Private" in str(error)


def test_crawler_response_size_is_bounded():
    from tools.url_security import URLSecurityError, fetch_public_url

    response = Mock()
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    response.status_code = 200
    response.headers = {"content-type": "text/html"}
    response.encoding = "utf-8"
    response.iter_bytes.return_value = [b"1234", b"5678"]
    client = Mock()
    client.stream.return_value = response
    resolver = Mock(return_value=[
        (None, None, None, None, ("93.184.216.34", 80))
    ])

    try:
        fetch_public_url(
            "http://example.com", client=client,
            resolver=resolver, max_bytes=5
        )
        assert False, "oversized response should have been rejected"
    except URLSecurityError as error:
        assert "maximum size" in str(error)


def test_windows_registry_scans_are_disabled_on_other_platforms():
    from tools import app_registry

    with patch.object(app_registry.sys, "platform", "linux"):
        assert app_registry.scan_registry_apps() == {}
        assert app_registry.scan_start_menu_apps() == {}
        assert app_registry.scan_uwp_apps() == {}


def test_app_launcher_does_not_use_shell_for_uwp_fallback():
    from tools.app_launcher_tool import AppLauncherTool

    tool = AppLauncherTool()
    tool._find_executable = Mock(return_value=None)
    tool._fallback_search = Mock(return_value="Package.App!Id")
    with patch("tools.app_launcher_tool.settings") as mock_settings, patch(
        "tools.app_launcher_tool.subprocess.Popen"
    ) as popen:
        mock_settings.app_launcher_enabled = True
        popen.side_effect = [FileNotFoundError(), Mock()]
        result = tool.execute("package")

    assert result["success"] is True
    assert popen.call_args_list[-1].args[0] == [
        "explorer.exe", "shell:AppsFolder\\Package.App!Id"
    ]
    assert "shell" not in popen.call_args_list[-1].kwargs
