"""G5 FIX: Zero-coverage gap — plugin engine install/security/cleanup tests.

Covers:
- install happy path (git clone mocked with a local fixture repo)
- plugin_path '..' escape rejection
- commonpath sibling-prefix bypass rejection (plugin_source)
- uninstall cleanup (package dir + DB entry)
- resolve-per-worker isolation

Run: .venv/bin/python -m pytest tests/test_plugin_engine.py -q
"""
import json
import os
from pathlib import Path
from types import SimpleNamespace

import pytest
import pytest_asyncio

from backend.database.session import AsyncSessionLocal, engine, Base, init_db
from storage.models import Base as StorageBase


# ── Fixture repo factory ─────────────────────────────────────

def _build_fixture_repo(repo_dir: Path) -> None:
    """Create a GitHub-like fixture repo layout on disk."""
    repo_dir.mkdir(parents=True, exist_ok=True)
    (repo_dir / "SKILL.md").write_text("# Repo Skill\n\nRoot instructions.\n", encoding="utf-8")
    # Root plugin manifest (happy path)
    (repo_dir / "plugin.json").write_text(json.dumps({
        "name": "Root Plugin",
        "version": "1.0.0",
        "description": "Root plugin for install happy path",
        "source": "",
    }), encoding="utf-8")
    # Sub-package with a manifest pointing at a sibling dir (sibling bypass test)
    sub = repo_dir / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "SKILL.md").write_text("# Sub Skill\n\nSub instructions.\n", encoding="utf-8")
    (sub / "plugin.json").write_text(json.dumps({
        "name": "Sub Plugin",
        "version": "1.0.0",
        "description": "Sub plugin with sibling source",
        "source": "../sub2",
    }), encoding="utf-8")
    # Sibling dir that must NOT be copied into the plugin package
    sub2 = repo_dir / "sub2"
    sub2.mkdir(exist_ok=True)
    (sub2 / "SECRET_MARKER.txt").write_text("sibling marker", encoding="utf-8")


def _fake_git_clone(returncode: int = 0, stderr: str = ""):
    """Return a subprocess.run stand-in that materializes the fixture repo."""
    def fake_run(cmd, **kwargs):
        if cmd and len(cmd) >= 3 and cmd[0] == "git" and cmd[1] == "clone":
            target = Path(cmd[-1])
            _build_fixture_repo(target)
            return SimpleNamespace(returncode=returncode, stderr=stderr)
        return SimpleNamespace(returncode=1, stderr="unsupported command")
    return fake_run


# ── DB fixture ───────────────────────────────────────────────

@pytest_asyncio.fixture(autouse=True)
async def setup_db(tmp_path):
    os.environ["AIC_DATA_DIR"] = str(tmp_path)
    await init_db()
    yield
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.drop_all)
        await conn.run_sync(Base.metadata.drop_all)
    async with engine.begin() as conn:
        await conn.run_sync(StorageBase.metadata.create_all)
        await conn.run_sync(Base.metadata.create_all)
    os.environ.pop("AIC_DATA_DIR", None)


@pytest.fixture(autouse=True)
def patch_git_clone(monkeypatch):
    import backend.plugin_engine as pe
    monkeypatch.setattr(pe.subprocess, "run", _fake_git_clone())


REPO_URL = "https://github.com/acme/test-plugin"


# ── Tests ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_install_happy_path():
    """Install a plugin from a mocked git clone; package + DB entry created."""
    from backend.plugin_engine import install_plugin, _plugin_root
    async with AsyncSessionLocal() as db:
        result = await install_plugin(db, REPO_URL)
        assert result["plugin_id"] == "root-plugin"
        assert result["version"] == "1.0.0"
        assert result["name"] == "Root Plugin"
        assert result["is_enabled"] is True
        pkg = Path(result["package_path"])
        assert pkg.exists() and pkg.is_dir()
        assert (pkg / "plugin.json").exists()
        assert result["components"]  # non-empty
        # install dir lives under the plugin root
        assert str(pkg.resolve()).startswith(str(_plugin_root().resolve()))


@pytest.mark.asyncio
async def test_install_rejects_dotdot_escape():
    """plugin_path='..' must raise ValueError (strict descendant check)."""
    from backend.plugin_engine import install_plugin
    async with AsyncSessionLocal() as db:
        with pytest.raises(ValueError, match="Invalid path"):
            await install_plugin(db, REPO_URL, plugin_path="..")


@pytest.mark.asyncio
async def test_manifest_source_sibling_bypass_rejected():
    """A manifest source resolving to a sibling prefix dir must be ignored."""
    from backend.plugin_engine import install_plugin
    async with AsyncSessionLocal() as db:
        result = await install_plugin(db, REPO_URL, plugin_path="sub")
        assert result["plugin_id"] == "sub-plugin"
        pkg = Path(result["package_path"])
        # The sibling dir (sub2/) must NOT be copied into the package.
        assert not (pkg / "SECRET_MARKER.txt").exists()
        # The plugin's own content is still installed.
        assert (pkg / "plugin.json").exists()


@pytest.mark.asyncio
async def test_uninstall_cleanup():
    """Uninstall removes both the DB entry and the package directory."""
    from backend.plugin_engine import install_plugin, uninstall_plugin, _plugin_root
    from storage.models import PluginEntry
    from sqlalchemy import select
    async with AsyncSessionLocal() as db:
        result = await install_plugin(db, REPO_URL)
        plugin_id = result["plugin_id"]
        pkg = Path(result["package_path"])
        assert pkg.exists()

        ok = await uninstall_plugin(db, plugin_id)
        assert ok is True
        assert not pkg.exists()
        assert not (_plugin_root() / plugin_id).exists()
        res = await db.execute(select(PluginEntry).where(PluginEntry.plugin_id == plugin_id))
        assert res.scalar_one_or_none() is None

        # Uninstalling an unknown plugin returns False
        assert await uninstall_plugin(db, "missing-plugin") is False


@pytest.mark.asyncio
async def test_resolve_plugins_per_worker_isolation():
    """Plugins assigned to one worker are not resolved for another worker."""
    from backend.plugin_engine import install_plugin, update_plugin, resolve_plugins_for_worker
    async with AsyncSessionLocal() as db:
        result = await install_plugin(db, REPO_URL)
        plugin_id = result["plugin_id"]

        # Unassigned → resolved for nobody
        assert await resolve_plugins_for_worker(db, "qa") == []
        assert await resolve_plugins_for_worker(db, "backend") == []

        # Assign to qa only
        await update_plugin(db, plugin_id, {"assigned_workers": ["qa"]})
        qa_plugins = await resolve_plugins_for_worker(db, "qa")
        assert [p["plugin_id"] for p in qa_plugins] == [plugin_id]
        assert await resolve_plugins_for_worker(db, "backend") == []

        # "all" assignment resolves for every worker
        await update_plugin(db, plugin_id, {"assigned_workers": ["all"]})
        assert await resolve_plugins_for_worker(db, "backend") != []
        assert await resolve_plugins_for_worker(db, "qa") != []

        # Disabled plugins are not resolved
        await update_plugin(db, plugin_id, {"is_enabled": False})
        assert await resolve_plugins_for_worker(db, "qa") == []


@pytest.mark.asyncio
async def test_update_plugin_repo_returns_update_status():
    """G4: update_plugin_repo re-clones and reports whether the version changed."""
    from backend.plugin_engine import install_plugin, update_plugin_repo
    async with AsyncSessionLocal() as db:
        result = await install_plugin(db, REPO_URL)
        plugin_id = result["plugin_id"]
        # Version unchanged → not updated
        status = await update_plugin_repo(db, plugin_id)
        assert status is not None
        assert status["updated"] is False
        assert status["version"] == "1.0.0"
        # Unknown plugin → None
        assert await update_plugin_repo(db, "missing-plugin") is None