"""Default ignore patterns, self-identification files, and glob resolution.

All pattern sets are ``frozenset`` — immutable defaults that the user's
editable config (``config.py``) copies into mutable lists.
"""

from __future__ import annotations

import fnmatch
from pathlib import Path


# ════════════════════════════════════════════════════════════════════
#  DEFAULT IGNORE SETS (immutable)
# ════════════════════════════════════════════════════════════════════

SFCIGNORE_FILE: str = ".sfcignore"

DEFAULT_IGNORE_DIRS: frozenset[str] = frozenset({
    # Python
    "__pycache__", ".mypy_cache", ".pytest_cache", ".tox", ".nox",
    ".eggs", ".ruff_cache", ".venv", "venv", "env",
    # VCS
    ".git", ".svn", ".hg",
    # IDE
    ".idea", ".vscode", ".vs",
    # Build output
    "dist", "build", "__MACOSX",
    # Language-specific
    "node_modules", ".terraform", ".gradle", ".cargo",
    ".next", ".nuxt", ".parcel-cache",
})

DEFAULT_IGNORE_FILES: frozenset[str] = frozenset({
    # OS junk
    ".DS_Store", "Thumbs.db", "desktop.ini",
    # SFC local ignore file
    SFCIGNORE_FILE,
    # VCS metadata
    ".gitignore", ".gitattributes", ".gitmodules",
    # Lock files
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "composer.lock",
    # Environment
    ".env", ".env.local", ".env.production",
})

DEFAULT_IGNORE_EXTENSIONS: frozenset[str] = frozenset({
    # Compiled / object
    ".pyc", ".pyo", ".pyd", ".class", ".o", ".obj",
    ".exe", ".dll", ".so", ".dylib", ".a", ".lib",
    # Images
    ".jpg", ".jpeg", ".png", ".gif", ".bmp",
    ".ico", ".svg", ".webp", ".tiff",
    # Media
    ".mp3", ".mp4", ".avi", ".mov", ".mkv",
    ".wav", ".flac", ".ogg",
    # Archives
    ".zip", ".tar", ".gz", ".bz2", ".xz",
    ".rar", ".7z", ".zst",
    # Documents (binary)
    ".pdf", ".doc", ".docx", ".xls", ".xlsx",
    ".ppt", ".pptx",
    # Databases
    ".db", ".sqlite", ".sqlite3",
    # Fonts / misc binary
    ".woff", ".woff2", ".ttf", ".eot", ".otf",
    # Source maps
    ".map",
})

# Files that belong to sfc itself — always excluded from collection
SELF_FILES: frozenset[str] = frozenset({
    "sfc.py", "sfc.pyz", SFCIGNORE_FILE,
})

COLLECTED_PREFIX: str = "collected_"
SFC_DOT_PREFIX: str = ".sfc-"


# ════════════════════════════════════════════════════════════════════
#  IN-APP HELP TEXT
# ════════════════════════════════════════════════════════════════════

HELP_GLOB: str = """\
 ╭─ Glob Patterns ───────────────────────────────────────────╮
 │                                                           │
 │  *        Match anything in one segment (e.g. *.py)       │
 │  ?        Match any single character                      │
 │  [seq]    Match any character in seq                      │
 │  [!seq]   Match any character NOT in seq                  │
 │                                                           │
 │  Examples:                                                │
 │    *.py           All .py files                           │
 │    src/*.ts       .ts files directly in src/              │
 │    **/test_*.py   Test files at any depth                 │
 │                                                           │
 ╰───────────────────────────────────────────────────────────╯"""

HELP_PRESETS: str = """\
 ╭─ Presets ─────────────────────────────────────────────────╮
 │                                                           │
 │  Save named file selections to .sfc-presets.json          │
 │                                                           │
 │  UI Actions:                                              │
 │  - Save:   Save current selection                         │
 │  - Use:    Load files from a preset                       │
 │  - Export: Collect preset files directly                  │
 │                                                           │
 │  CLI Examples:                                            │
 │  $ sfc preset save my_preset "src/*.py"                   │
 │  $ sfc preset my_preset                                   │
 │                                                           │
 ╰───────────────────────────────────────────────────────────╯"""

HELP_FILTERS: str = """\
 ╭─ Filters & Ignore ────────────────────────────────────────╮
 │                                                           │
 │  Ignore Categories (via Settings):                        │
 │  - Dirs:  Skip entire folders (e.g. node_modules, .git)   │
 │  - Files: Skip exact filenames (e.g. .DS_Store, .env)     │
 │  - Exts:  Skip by suffix (e.g. .pyc, .pdf, .zip)          │
 │                                                           │
 │  Features:                                                │
 │  - Comment Killer: Strips comments/docstrings from .py    │
 │  - Browse Filter (/): Live substring search               │
 │  - Glob Pattern (p): Select by pattern in browse view     │
 │                                                           │
 ╰───────────────────────────────────────────────────────────╯"""


# ════════════════════════════════════════════════════════════════════
#  RESOLUTION HELPERS
# ════════════════════════════════════════════════════════════════════

def load_sfcignore(root: Path) -> set[str]:
    """Load local ignore patterns from ``<root>/.sfcignore``."""
    fp: Path = root / SFCIGNORE_FILE
    if not fp.is_file():
        return set()

    patterns: set[str] = set()
    try:
        lines = fp.read_text(encoding="utf-8").splitlines()
    except OSError:
        return patterns

    for raw in lines:
        line: str = raw.strip()
        if not line or line.startswith("#"):
            continue
        patterns.add(line.rstrip("/\\"))

    return patterns


def matches_pattern(rel_path: str, name: str, pattern: str) -> bool:
    """Return *True* if *rel_path* or *name* matches *pattern* (fnmatch).

    Tries three variants so both ``*.py`` and ``sfc/app.py`` work
    intuitively from any context.
    """
    return (
        fnmatch.fnmatch(rel_path, pattern)
        or fnmatch.fnmatch(name, pattern)
        or fnmatch.fnmatch(rel_path, "*/" + pattern)
    )


def resolve_patterns(
    root: Path,
    patterns: list[str],
    all_files: list[Path],
) -> tuple[list[Path], list[str]]:
    """Resolve user-supplied paths / dirs / globs against *all_files*.

    Returns
    -------
    matched
        Sorted list of files that matched at least one pattern.
    unmatched
        Patterns that produced zero hits.
    """
    picked: list[Path] = []
    seen: set[Path] = set()
    unmatched: list[str] = []

    for raw in patterns:
        pat: str = raw.strip().strip("\"'").rstrip("/\\")
        if not pat:
            continue

        hit_count_before: int = len(picked)
        target: Path = root / pat

        # 1) Exact file match
        if target.is_file() and target not in seen:
            picked.append(target)
            seen.add(target)
            continue

        # 2) Directory → every file underneath
        if target.is_dir():
            for f in all_files:
                if f.is_relative_to(target) and f not in seen:
                    picked.append(f)
                    seen.add(f)
            if len(picked) > hit_count_before:
                continue

        # 3) Glob / fnmatch against relative paths
        for f in all_files:
            rel: str = str(f.relative_to(root)).replace("\\", "/")
            if matches_pattern(rel, f.name, pat) and f not in seen:
                picked.append(f)
                seen.add(f)

        if len(picked) == hit_count_before:
            unmatched.append(pat)

    picked.sort(key=lambda f: str(f.relative_to(root)))
    return picked, unmatched
