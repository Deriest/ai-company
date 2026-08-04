"""Unit tests for the shared workspace path resolver (path_utils.py).

Covers the security contract that was previously duplicated across
tool_executor._resolve_path, workers.tools._resolve_path and
tool_dispatcher._resolve_path:
- normal path OK
- '..' escape blocked
- absolute path blocked
- sibling-prefix bypass blocked (/root2/... when root is /root)
- symlink escape blocked (symlink inside workspace pointing outside)
- empty path behavior (resolves to the workspace root)
- root itself allowed
"""
import asyncio
import os
import pytest

from backend.services.path_utils import resolve_workspace_path
from backend.services.tool_executor import WorkerToolExecutor


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


def test_normal_relative_path_ok(root):
    candidate = resolve_workspace_path(root, "sub/file.txt")
    assert candidate == os.path.realpath(os.path.join(root, "sub", "file.txt"))
    assert candidate.startswith(os.path.realpath(root) + os.sep)


def test_single_dot_and_plain_ok(root):
    assert resolve_workspace_path(root, ".") == os.path.realpath(root)
    assert resolve_workspace_path(root, "./sub") == os.path.realpath(os.path.join(root, "sub"))


def test_dotdot_escape_blocked(root):
    with pytest.raises(ValueError):
        resolve_workspace_path(root, "../escape.txt")
    with pytest.raises(ValueError):
        resolve_workspace_path(root, "a/../../escape.txt")
    with pytest.raises(ValueError):
        resolve_workspace_path(root, "../../../etc/passwd")


def test_absolute_path_blocked(root):
    with pytest.raises(ValueError):
        resolve_workspace_path(root, "/etc/passwd")
    # An absolute path pointing outside the workspace (sibling of root)
    # must be rejected too.
    with pytest.raises(ValueError):
        resolve_workspace_path(root, os.path.join(os.path.dirname(root), "outside.txt"))


def test_sibling_prefix_bypass_blocked(tmp_path):
    # root = /tmp/xxx/root; sibling /tmp/xxx/root2 must NOT be reachable.
    root = tmp_path / "root"
    root.mkdir()
    sibling = tmp_path / "root2"
    sibling.mkdir()
    with pytest.raises(ValueError):
        resolve_workspace_path(str(root), "../root2/secret.txt")
    # A candidate whose string starts with root but is a sibling directory
    # (root2) must be rejected by the root + os.sep boundary check.
    with pytest.raises(ValueError):
        resolve_workspace_path(str(root), str(sibling / "secret.txt"))


def test_empty_path_resolves_to_root(root):
    assert resolve_workspace_path(root, "") == os.path.realpath(root)


def test_root_itself_allowed(root):
    assert resolve_workspace_path(root, root) == os.path.realpath(root)


def test_normalizes_workspace_root(tmp_path):
    # A trailing-slash workspace root must be normalized identically.
    root = tmp_path / "ws"
    root.mkdir()
    assert resolve_workspace_path(str(root) + os.sep, "f.txt") == os.path.realpath(root / "f.txt")


# ── F9: symlink escape ─────────────────────────────────────

def test_symlink_file_escape_blocked(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    link = ws / "evil.txt"
    link.symlink_to(secret)
    with pytest.raises(ValueError):
        resolve_workspace_path(str(ws), "evil.txt")


def test_symlink_dir_escape_blocked(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.txt").write_text("secret")
    link = ws / "sub"
    link.symlink_to(outside)
    with pytest.raises(ValueError):
        resolve_workspace_path(str(ws), "sub/secret.txt")
    # Nested symlink inside a normal subdirectory.
    sub = ws / "real"
    sub.mkdir()
    link2 = sub / "escape"
    link2.symlink_to(outside / "secret.txt")
    with pytest.raises(ValueError):
        resolve_workspace_path(str(ws), "real/escape")


def test_symlink_read_blocked_via_executor(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    secret = tmp_path / "secret.txt"
    secret.write_text("secret")
    link = ws / "evil.txt"
    link.symlink_to(secret)
    executor = WorkerToolExecutor(workspace_root=str(ws))
    result = asyncio.run(executor.read_file("evil.txt"))
    assert result.success is False
    assert "outside" in (result.error or "").lower()


def test_symlink_write_blocked_via_executor(tmp_path):
    ws = tmp_path / "ws"
    ws.mkdir()
    victim = tmp_path / "victim.txt"
    victim.write_text("original")
    link = ws / "evil.txt"
    link.symlink_to(victim)
    executor = WorkerToolExecutor(workspace_root=str(ws))
    result = asyncio.run(executor.write_file("evil.txt", "pwned"))
    assert result.success is False
    # The victim file must be untouched.
    assert victim.read_text() == "original"