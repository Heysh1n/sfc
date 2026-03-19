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
    "sfc.py", "sfc.pyz",
})

COLLECTED_PREFIX: str = "collected_"
SFC_DOT_PREFIX: str = ".sfc-"


# ════════════════════════════════════════════════════════════════════
#  IN-APP HELP TEXT
# ════════════════════════════════════════════════════════════════════

HELP_GLOB: str = """\
 ╭─ Glob Pattern Reference ──────────────────────────────────╮
 │                                                           │
 │  *          matches everything inside one segment         │
 │  ?          matches any single character                  │
 │  [seq]      matches any character in seq                  │
 │  [!seq]     matches any character NOT in seq              │
 │  **         not supported by fnmatch (use path segments)  │
 │                                                           │
 │  Examples:                                                │
 │    *.py             all Python files (any depth)          │
 │    src/*.ts         .ts files directly in src/            │
 │    test_*.py        files starting with test_             │
 │    *.service.ts     Angular services                      │
 │    config/*         everything inside config/             │
 │    **/utils/*.py    utils dirs at any depth               │
 │                                                           │
 ╰───────────────────────────────────────────────────────────╯"""

HELP_PRESETS: str = """\
 ╭─ Presets Guide ───────────────────────────────────────────╮
 │                                                          │
 │  Presets save named file selections for quick reuse.     │
 │  Stored per-project in .sfc-presets.json at project root.│
 │                                                          │
 │  Save:   select files → Presets → Save                   │
 │  Use:    Presets → Use → pick number                     │
 │  Export: Presets → Export → direct collect + clipboard    │
 │  Delete: Presets → Delete → pick number                  │
 │                                                          │
 │  CLI:                                                    │
 │    sfc preset save myconf "src/config/*" ".env.example"  │
 │    sfc preset myconf                                     │
 │    sfc preset list                                       │
 │    sfc preset delete myconf                              │
 │                                                          │
 ╰──────────────────────────────────────────────────────────╯"""

HELP_FILTERS: str = """\
 ╭─ Filter & Ignore Guide ──────────────────────────────────╮
 │                                                          │
 │  Three ignore categories (editable in Settings):         │
 │                                                          │
 │  Directories:  folder names skipped during scan          │
 │     e.g.  node_modules, .git, __pycache__                │
 │                                                          │
 │  Files:        exact filenames always excluded            │
 │     e.g.  .DS_Store, package-lock.json, .env             │
 │                                                          │
 │  Extensions:   file suffixes excluded by extension        │
 │     e.g.  .pyc, .jpg, .zip, .pdf                        │
 │                                                          │
 │  Comment Killer (v4.0):                                  │
 │     Settings → Strip Explanations → ON                   │
 │     Removes docstrings + comments from .py files (AST)   │
 │                                                          │
 │  Browse filter (/):  live substring search on paths      │
 │  Browse pattern (p): select by glob in current view      │
 │  Reset to defaults:  Settings → Ignoring → Reset         │
 │                                                          │
 ╰──────────────────────────────────────────────────────────╯"""


# ════════════════════════════════════════════════════════════════════
#  RESOLUTION HELPERS
# ════════════════════════════════════════════════════════════════════

def matches_pattern(rel_path: str, name: str, pattern: str) -> bool:
    """Return *True* if *rel_path* or *name* matches *pattern* (fnmatch).

    Tries three variants so both ``*.py`` and ``src/main.py`` work
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