from pathlib import Path

import pytest

import server


def test_relative_path_stays_in_first_root(tmp_path, monkeypatch):
    monkeypatch.setattr(
        server,
        "SETTINGS",
        server.Settings(
            roots=(tmp_path.resolve(),),
            deny_names=(".ssh",),
            max_read_bytes=1024,
            max_write_bytes=1024,
            shell_enabled=True,
            shell="cmd",
            shell_timeout=5,
            shell_max_output=1024,
            shell_allow=("echo",),
        ),
    )
    assert server.resolve_scoped_path("a.txt") == (tmp_path / "a.txt").resolve()


def test_parent_escape_is_rejected(tmp_path, monkeypatch):
    settings = server.Settings(
        roots=(tmp_path.resolve(),),
        deny_names=(".ssh",),
        max_read_bytes=1024,
        max_write_bytes=1024,
        shell_enabled=True,
        shell="cmd",
        shell_timeout=5,
        shell_max_output=1024,
        shell_allow=("echo",),
    )
    monkeypatch.setattr(server, "SETTINGS", settings)
    with pytest.raises(server.PolicyError):
        server.resolve_scoped_path(str(Path(tmp_path).parent / "escape.txt"))


def test_shell_allowlist(tmp_path, monkeypatch):
    settings = server.Settings(
        roots=(tmp_path.resolve(),),
        deny_names=(".ssh",),
        max_read_bytes=1024,
        max_write_bytes=1024,
        shell_enabled=True,
        shell="cmd",
        shell_timeout=5,
        shell_max_output=1024,
        shell_allow=("echo",),
    )
    monkeypatch.setattr(server, "SETTINGS", settings)
    assert server.validate_shell("echo hello", tmp_path) == "echo"
    with pytest.raises(server.PolicyError):
        server.validate_shell("unknown-tool test", tmp_path)
