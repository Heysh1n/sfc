#!/usr/bin/env python3
"""
SFC Build Script - Unified ZipApp Builder with Auto-Versioning
"""

import re
import shutil
import sys
import zipapp
from pathlib import Path

DIST = Path("dist")
STAGING = Path("_build_staging")
PKG = Path("sfc")
APP_NAME = "sfc"


def clean() -> None:
    """Remove all build artifacts."""
    for d in (DIST, STAGING, Path("build"), Path(".zipapp_root")):
        if d.is_dir():
            shutil.rmtree(d)
    for cache in Path(".").rglob("__pycache__"):
        shutil.rmtree(cache, ignore_errors=True)
    for pyc in Path(".").rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    for spec in Path(".").glob("*.spec"):
        spec.unlink(missing_ok=True)
    
    Path(f"{APP_NAME}.pyz").unlink(missing_ok=True)
    print("🧹 Cleaned build artifacts")


def sync_version() -> str:
    """Extracts version from pyproject.toml and safely updates sfc/version.py"""
    toml_path = Path("pyproject.toml")
    version_file = PKG / "version.py"

    if not toml_path.exists() or not version_file.exists():
        print("⚠️ Missing files for version sync")
        return "unknown"

    toml_content = toml_path.read_text(encoding="utf-8")
    match = re.search(r'^version\s*=\s*["\']([^"\']+)["\']', toml_content, re.MULTILINE)
    if not match:
        return "unknown"
    version = match.group(1)
    
    v_content = version_file.read_text(encoding="utf-8")
    v_content = re.sub(r'^VERSION\s*=\s*["\'].*?["\']', f'VERSION = "{version}"', v_content, flags=re.MULTILINE)
    v_content = re.sub(r'^__version__\s*=\s*["\'].*?["\']', f'__version__ = "{version}"', v_content, flags=re.MULTILINE)
    version_file.write_text(v_content, encoding="utf-8")
    
    print(f"🔄 Synced version: v{version}")
    return version


def build() -> Path:
    """Build dist/sfc.pyz portable archive."""
    clean()
    version = sync_version()
    
    DIST.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)

    shutil.copytree(PKG, STAGING / "sfc", dirs_exist_ok=True)

    for cache in STAGING.rglob("__pycache__"):
        shutil.rmtree(cache)
    for pyc in STAGING.rglob("*.pyc"):
        pyc.unlink()

    out = DIST / f"{APP_NAME}.pyz"
    
    zipapp.create_archive(
        source=STAGING,
        target=out,
        interpreter="/usr/bin/env python3",
        main="sfc.__main__:main",
        compressed=True,
    )

    shutil.rmtree(STAGING)

    root_out = Path(f"{APP_NAME}.pyz")
    shutil.copy(out, root_out)

    size_kb = out.stat().st_size / 1024
    print(f"✅ Built: {out}  ({size_kb:.1f} KB)")
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "build"
    if cmd == "clean":
        clean()
    elif cmd in ("build", "all", "zipapp"):
        build()
    else:
        print(f"Unknown command: {cmd}")
        print("Usage: python build.py [build|clean|all]")
        sys.exit(1)