#!/usr/bin/env python3
"""Build sfc.pyz with correct package structure."""

from __future__ import annotations

import shutil
import zipapp
from pathlib import Path

DIST = Path("dist")
STAGING = Path("_build_staging")
PKG = Path("sfc")
APP_NAME = "sfc"


def clean() -> None:
    for d in (DIST, STAGING):
        if d.is_dir():
            shutil.rmtree(d)
    print("🧹 Cleaned")


def build() -> Path:
    clean()
    DIST.mkdir(parents=True, exist_ok=True)
    STAGING.mkdir(parents=True, exist_ok=True)

    # Copy package into staging as a subdirectory (preserves relative imports)
    shutil.copytree(PKG, STAGING / "sfc", dirs_exist_ok=True)

    # Remove __pycache__
    for cache in (STAGING / "sfc").rglob("__pycache__"):
        shutil.rmtree(cache)

    # Top-level __main__.py that uses absolute imports
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


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "clean":
        clean()
    else:
        build()