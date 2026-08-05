#!/usr/bin/env python3
"""Verify every requirement in backend/requirements.txt is importable from the
packaged Python runtimes (python-linux + python-win) bundled into the app.

WHY: a dependency-only-in-dev-venv historically shipped in a release and broke
the installed app at startup (e.g. PyJWT vs python-jose: packaged runtimes ship
python-jose, dev venv had PyJWT -> ModuleNotFoundError on the installed app).
This script must pass before `scripts/release.sh` is allowed to build.

Usage:
    python3 scripts/verify_runtime_deps.py

Exit code 0 = all packaged runtimes satisfy requirements.txt.
Exit code 1 = at least one required module is missing from a packaged runtime.
"""
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
REQS = ROOT / "backend" / "requirements.txt"
RUNTIMES = {
    "python-linux": ROOT / "app" / "packaging" / "runtimes" / "python-linux",
    "python-win": ROOT / "app" / "packaging" / "runtimes" / "python-win",
}
# site-packages layout differs per platform
SITE_PACKAGES = {
    "python-linux": "lib/python3.12/site-packages",
    "python-win": "Lib/site-packages",
}
# module name for each pip package (only the ones that matter for import parity)
# key = pip package name (lowercase), value = importable module(s)
PACKAGE_MODULES = {
    "python-jose[cryptography]": ["jose"],
    "python-jose": ["jose"],
    "pyjwt": ["jwt"],
    "fastapi": ["fastapi"],
    "uvicorn": ["uvicorn"],
    "sqlalchemy": ["sqlalchemy"],
    "aiosqlite": ["aiosqlite"],
    "httpx": ["httpx"],
    "pydantic": ["pydantic"],
    "pydantic-settings": ["pydantic_settings"],
    "python-dotenv": ["dotenv"],
    "python-multipart": ["multipart"],
    "tenacity": ["tenacity"],
    "sentence-transformers": ["sentence_transformers"],
    "numpy": ["numpy"],
    "sse-starlette": ["sse_starlette"],
}


def pip_name(req: str) -> str:
    """Extract the canonical pip package name from a requirements line."""
    req = req.strip()
    if not req or req.startswith("#") or req.startswith("-"):
        return ""
    name = req.split("==")[0].split(">=")[0].split("<")[0].split(";")[0].split("[")[0]
    return name.strip().lower().replace("_", "-")


def find_module(site_packages: pathlib.Path, module: str) -> bool:
    """Check a module is importable from the runtime's site-packages."""
    if not site_packages.exists():
        return False
    return (site_packages / module).exists() or (
        site_packages / f"{module}.py"
    ).exists()


def main() -> int:
    reqs = [l for l in REQS.read_text().splitlines() if l.strip() and not l.startswith("#")]
    failures = []

    for runtime_name, runtime_root in RUNTIMES.items():
        sp = runtime_root / SITE_PACKAGES[runtime_name]
        if not sp.exists():
            failures.append(f"[{runtime_name}] site-packages NOT FOUND: {sp}")
            continue
        for line in reqs:
            name = pip_name(line)
            modules = PACKAGE_MODULES.get(name)
            if not modules:
                continue  # not in the import-parity map (build-only / transitive)
            for mod in modules:
                if not find_module(sp, mod):
                    failures.append(
                        f"[{runtime_name}] MISSING module '{mod}' "
                        f"(required by '{line}') in {sp}"
                    )

    if failures:
        print("❌ PACKAGED RUNTIME DEPENDENCY MISMATCH — DO NOT RELEASE")
        for f in failures:
            print(f"   {f}")
        print("\nFix: install the missing module into both packaged runtimes, e.g.\n"
              "  app/packaging/runtimes/python-linux/bin/python -m pip install <pkg>\n"
              "  (and the same for python-win via its python.exe + pip).")
        return 1

    print("✅ Packaged runtimes (linux + win) satisfy all import-critical requirements.")
    return 0


if __name__ == "__main__":
    sys.exit(main())