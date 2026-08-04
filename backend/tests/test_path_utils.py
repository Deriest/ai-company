"""Unit tests for the shared workspace path resolver (path_utils.py).

Covers the security contract that was previously duplicated across
tool_executor._resolve_path, workers.tools._resolve_path and
tool_dispatcher._resolve_path:
- normal path OK
- '..' escape blocked
- absolute path blocked
- sibling-prefix bypass blocked (/root2/... when root is /root)
- empty path behavior (resolves to the workspace root)
- root itself allowed
"""
import os
import pytest

from backend.services.path_utils import resolve_workspace_path


@pytest.fixture
def root(tmp_path):
    return str(tmp_path)


def test_normal_relative_path_ok(root):
    candidate = resolve_workspace_path(root, "sub/file.txt")
    assert candidate == os.path.abspath(os.path.join(root, "sub", "file.txt"))
    assert candidate.startswith(os.path.abspath(root) + os.sep)


def test_single_dot_and_plain_ok(root):
    assert resolve_workspace_path(root, ".") == os.path.abspath(root)
    assert resolve_workspace_path(root, "./sub") == os.path.abspath(os.path.join(root, "sub"))


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
    assert resolve_workspace_path(root, "") == os.path.abspath(root)


def test_root_itself_allowed(root):
    assert resolve_workspace_path(root, root) == os.path.abspath(root)


def test_normalizes_workspace_root(tmp_path):
    # A trailing-slash workspace root must be normalized identically.
    root = tmp_path / "ws"
    root.mkdir()
    assert resolve_workspace_path(str(root) + os.sep, "f.txt") == os.path.abspath(root / "f.txt")