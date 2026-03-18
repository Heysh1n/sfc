# fc/core.py
"""Core file scanning, pattern resolution, safe reading."""

import os
import fnmatch
from pathlib import Path

from fc.config import IGNORE_DIRS, IGNORE_FILES, IGNORE_EXTENSIONS, get_self_files


def get_all_files(root: str | Path, extra_ignore: set[str] | None = None) -> list[Path]:
    """Recursively collect all project files, respecting ignore rules."""
    ignore = IGNORE_DIRS | (extra_ignore or set())
    self_files = get_self_files()
    root_path = Path(root).resolve()
    result: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root_path):
        dirnames[:] = sorted(d for d in dirnames if d not in ignore)
        for fn in sorted(filenames):
            fp = Path(dirpath) / fn
            if fn in self_files or fn in IGNORE_FILES:
                continue
            if fn.startswith("collected_") or fn.startswith(".fc-"):
                continue
            if fp.suffix.lower() in IGNORE_EXTENSIONS:
                continue
            result.append(fp)

    return result


def resolve_patterns(
    root: Path, patterns: list[str], all_files: list[Path]
) -> list[Path]:
    """Resolve a list of paths / dirs / globs into actual file paths."""
    picked: list[Path] = []
    seen: set[Path] = set()

    for pat in patterns:
        pat = pat.strip().strip("\"'").rstrip("/")
        if not pat:
            continue

        target = root / pat

        # 1. Exact file
        if target.is_file():
            if target not in seen:
                picked.append(target)
                seen.add(target)
            continue

        # 2. Directory → all files inside
        if target.is_dir():
            for f in all_files:
                try:
                    f.relative_to(target)
                    if f not in seen:
                        picked.append(f)
                        seen.add(f)
                except ValueError:
                    pass
            continue

        # 3. Glob pattern
        found = False
        for f in all_files:
            rel = str(f.relative_to(root)).replace("\\", "/")
            name = f.name
            if (
                fnmatch.fnmatch(rel, pat)
                or fnmatch.fnmatch(name, pat)
                or fnmatch.fnmatch(rel, "*/" + pat)
            ):
                if f not in seen:
                    picked.append(f)
                    seen.add(f)
                    found = True

        if not found:
            from fc.colors import C
            print(f"  {C.YELLOW}⚠️  Not found: {pat}{C.RESET}")

    return sorted(picked, key=lambda f: str(f.relative_to(root)))


def read_safe(fp: Path) -> str:
    """Read file content trying multiple encodings."""
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return fp.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as e:
            return f"[ERR: {e}]"
    return "[ERR: encoding]"