#!/usr/bin/env python3
"""Convenience build script — wraps ``make zipapp`` for Windows users
who don't have make, and for CI pipelines.

Usage:
    python build.py            # build .pyz
    python build.py clean      # remove artifacts
    python build.py all        # alias for build
    python build.py check      # verify PyInstaller prerequisites
"""

from __future__ import annotations

import shutil
import sys
import sysconfig
import zipapp
from pathlib import Path

DIST = Path("dist")
STAGING = Path("_build_staging")
PKG = Path("sfc")
APP_NAME = "sfc"


def clean() -> None:
    """Remove all build artifacts."""
    for d in (DIST, STAGING, Path("build")):
        if d.is_dir():
            shutil.rmtree(d)
    for spec in Path(".").glob("*.spec"):
        spec.unlink()
    for cache in Path(".").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    print("🧹 Cleaned")


def build() -> Path:
    """Build ``dist/sfc.pyz`` portable archive."""
    clean()
    DIST.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)

    # Copy package into staging (preserves relative imports)
    shutil.copytree(PKG, STAGING / "sfc", dirs_exist_ok=True)

    # Strip __pycache__ / .pyc
    for cache in (STAGING / "sfc").rglob("__pycache__"):
        shutil.rmtree(cache)
    for pyc in (STAGING / "sfc").rglob("*.pyc"):
        pyc.unlink()

    # Top-level __main__.py
    (STAGING / "__main__.py").write_text(
        "import sys\n"
        "from sfc.app import run\n"
        "run(sys.argv[1:])\n",
        encoding="utf-8",
    )

    out = DIST / f"{APP_NAME}.pyz"
    zipapp.create_archive(
        source=STAGING,
        target=out,
        interpreter="/usr/bin/env python3",
        compressed=True,
    )

    shutil.rmtree(STAGING)

    size_kb = out.stat().st_size / 1024
    print(f"✅ Built: {out}  ({size_kb:.1f} KB)")
    print(f"   Run:   ./{out}  or  python {out}")
    return out


def check_pyinstaller() -> None:
    """Check whether PyInstaller can work in this environment."""
    shared = sysconfig.get_config_var("Py_ENABLE_SHARED")
    ldlib = sysconfig.get_config_var("LDLIBRARY") or ""
    pi = shutil.which("pyinstaller")

    print()
    print(f"  Python:         {sys.executable}")
    print(f"  Version:        {sys.version.split()[0]}")
    print(f"  Platform:       {sys.platform}")
    print(f"  Shared lib:     {'YES' if shared else 'NO  ← PyInstaller will fail'}")
    print(f"  LDLIBRARY:      {ldlib or '(none)'}")
    print(f"  PyInstaller:    {pi or 'NOT INSTALLED'}")
    print()

    if not shared:
        print("  ❌ Python was NOT built with --enable-shared")
        print()
        print("  Solutions:")
        print('    1. Use "python build.py" for .pyz (works everywhere)')
        print("    2. Rebuild Python with --enable-shared:")
        print('       pyenv: PYTHON_CONFIGURE_OPTS="--enable-shared" pyenv install 3.12')
        print("       conda: conda install python  (always shared)")
        print()
        sys.exit(1)

    if not pi:
        print("  ❌ PyInstaller not installed")
        print("     pip install pyinstaller")
        sys.exit(1)

    print("  ✅ Ready for PyInstaller builds")
    print()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "clean":
        clean()
    elif cmd in ("build", "all", "zipapp"):
        build()
    elif cmd == "check":
        check_pyinstaller()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python build.py [build|clean|all|check]")
        sys.exit(1)