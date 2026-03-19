"""File scanning, AST comment killer, tree rendering, and output assembly.

v4.0 additions:
  - ``strip_python_explanations()`` — uses the ``ast`` module to surgically
    remove all docstrings (module / class / function) and ``#`` comments
    from ``.py`` files.  No regex.  Preserves functional code exactly.
"""

from __future__ import annotations

import ast
import io
import os
import tokenize
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .config import AppConfig


# ════════════════════════════════════════════════════════════════════
#  UTILITY HELPERS
# ════════════════════════════════════════════════════════════════════

def term_width() -> int:
    """Current terminal column count (fallback 80)."""
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def fmt_size(n: int) -> str:
    """Human-readable byte size."""
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f}M"
    if n >= 1_024:
        return f"{n / 1_024:.1f}K"
    return f"{n}B"


def read_safe(fp: Path) -> str:
    """Read file trying multiple encodings, never raises."""
    for enc in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            return fp.read_text(encoding=enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        except Exception as exc:
            return f"[ERR: {exc}]"
    return "[ERR: encoding]"


# ════════════════════════════════════════════════════════════════════
#  AST COMMENT KILLER (v4.0)
# ════════════════════════════════════════════════════════════════════

def _is_docstring_node(node: ast.AST) -> bool:
    """Return True if *node* is an ``ast.Expr`` wrapping a string constant
    (i.e. a docstring)."""
    return (
        isinstance(node, ast.Expr)
        and isinstance(node.value, (ast.Constant, ast.Str))
        and isinstance(
            node.value.s if isinstance(node.value, ast.Str) else node.value.value,
            str,
        )
    )


def _collect_docstring_lines(source: str) -> set[int]:
    """Parse *source* with ``ast`` and return the set of 1-based line numbers
    that belong to docstrings (module-level, class-level, function-level).

    Uses AST — not regex — to identify docstrings precisely.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return set()

    docstring_lines: set[int] = set()

    for node in ast.walk(tree):
        # Containers that can have docstrings: Module, ClassDef, FunctionDef, AsyncFunctionDef
        body: list[ast.stmt] | None = None
        if isinstance(node, ast.Module):
            body = node.body
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body

        if body and body and _is_docstring_node(body[0]):
            ds_node = body[0]
            for line_no in range(ds_node.lineno, ds_node.end_lineno + 1):  # type: ignore[union-attr]
                docstring_lines.add(line_no)

    return docstring_lines


def _strip_hash_comments(source: str) -> str:
    """Remove ``# comment`` tokens from Python source using the ``tokenize``
    module.  Preserves shebangs (``#!``) on line 1 and ``# type:`` / ``# noqa``
    pragmas.

    Returns the source with comment tokens replaced by empty strings and
    trailing whitespace cleaned up per line.
    """
    PRAGMAS: tuple[str, ...] = (
        "# type:", "# noqa", "# pragma:", "# pylint:", "# fmt:",
        "# isort:", "# mypy:", "# pyright:",
    )

    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError:
        return source

    # Build set of (row, col_offset) for comment tokens to remove
    remove_positions: set[tuple[int, int]] = set()

    for tok in tokens:
        if tok.type != tokenize.COMMENT:
            continue
        # Keep shebangs
        if tok.start[0] == 1 and tok.string.startswith("#!"):
            continue
        # Keep pragmas
        stripped = tok.string.strip()
        if any(stripped.startswith(p) for p in PRAGMAS):
            continue
        remove_positions.add(tok.start)

    if not remove_positions:
        return source

    lines = source.splitlines(keepends=True)
    result: list[str] = []

    for line_no_0, line in enumerate(lines):
        line_no_1 = line_no_0 + 1
        modified = line
        # Check if any comment on this line should be removed
        for (row, col) in sorted(remove_positions, reverse=True):
            if row == line_no_1:
                # Remove from col to end-of-content (keep newline)
                before = line[:col].rstrip()
                newline = ""
                if line.endswith("\r\n"):
                    newline = "\r\n"
                elif line.endswith("\n"):
                    newline = "\n"
                elif line.endswith("\r"):
                    newline = "\r"
                if before:
                    modified = before + newline
                else:
                    # Entire line was just a comment — produce empty line
                    modified = ""
        result.append(modified)

    return "".join(result)


def _strip_docstring_lines(source: str, ds_lines: set[int]) -> str:
    """Remove lines identified as docstrings.  Consecutive blank lines
    left behind are collapsed to a single blank line."""
    if not ds_lines:
        return source

    lines = source.splitlines(keepends=True)
    result: list[str] = []

    for line_no_0, line in enumerate(lines):
        line_no_1 = line_no_0 + 1
        if line_no_1 in ds_lines:
            continue
        result.append(line)

    return "".join(result)


def _collapse_blank_lines(source: str) -> str:
    """Collapse runs of 3+ consecutive blank lines into 2 (PEP 8 style)."""
    lines = source.split("\n")
    result: list[str] = []
    blank_count: int = 0

    for line in lines:
        if line.strip() == "":
            blank_count += 1
            if blank_count <= 2:
                result.append(line)
        else:
            blank_count = 0
            result.append(line)

    # Strip trailing blanks
    while result and result[-1].strip() == "":
        result.pop()

    return "\n".join(result) + "\n" if result else ""


def strip_python_explanations(source: str) -> str:
    """Strip all docstrings and hash-comments from Python *source*.

    Pipeline:
      1. AST pass → identify docstring line ranges
      2. Remove docstring lines
      3. tokenize pass → remove ``#`` comments (preserving pragmas)
      4. Collapse excessive blank lines

    If the source has a ``SyntaxError``, it is returned unchanged.
    """
    # Step 1: AST → docstring lines
    ds_lines = _collect_docstring_lines(source)

    # Step 2: Remove docstrings
    cleaned = _strip_docstring_lines(source, ds_lines)

    # Step 3: Remove hash comments
    cleaned = _strip_hash_comments(cleaned)

    # Step 4: Collapse blanks
    cleaned = _collapse_blank_lines(cleaned)

    return cleaned


# ════════════════════════════════════════════════════════════════════
#  FILE SCANNING
# ════════════════════════════════════════════════════════════════════

def _is_self_file(name: str) -> bool:
    """Files belonging to sfc itself — always skip."""
    from .patterns import SELF_FILES, COLLECTED_PREFIX, SFC_DOT_PREFIX

    return (
        name in SELF_FILES
        or name.startswith(COLLECTED_PREFIX)
        or name.startswith(SFC_DOT_PREFIX)
    )


def get_all_files(
    root: Path,
    cfg: AppConfig,
    extra_ignore: set[str] | None = None,
) -> list[Path]:
    """Recursively collect project files respecting config ignore rules.

    Parameters
    ----------
    root
        Project root directory (resolved).
    cfg
        Current application config (ignore lists read from here).
    extra_ignore
        Optional additional directory names to skip (e.g. from CLI ``-i``).

    Returns
    -------
    list[Path]
        Sorted list of absolute paths.
    """
    ignore_dirs: set[str] = cfg.ignore_dirs_set()
    if extra_ignore:
        ignore_dirs |= extra_ignore
    ignore_files: set[str] = cfg.ignore_files_set()
    ignore_ext: set[str] = cfg.ignore_ext_set()
    root = root.resolve()
    result: list[Path] = []

    for dirpath, dirnames, filenames in os.walk(root):
        # Prune ignored directories in-place (also sorts for determinism)
        dirnames[:] = sorted(d for d in dirnames if d not in ignore_dirs)

        for fn in sorted(filenames):
            if fn in ignore_files:
                continue
            if _is_self_file(fn):
                continue
            fp = Path(dirpath) / fn
            if fp.suffix.lower() in ignore_ext:
                continue
            result.append(fp)

    return result


# ════════════════════════════════════════════════════════════════════
#  CONTENT READING (with optional comment stripping)
# ════════════════════════════════════════════════════════════════════

def read_file_content(fp: Path, strip: bool = False) -> str:
    """Read a file and optionally strip comments/docstrings for ``.py`` files.

    Parameters
    ----------
    fp
        Absolute path to the file.
    strip
        If *True* and the file is a ``.py`` file, run the AST comment killer.
    """
    content = read_safe(fp)
    if content.startswith("[ERR:"):
        return content
    if strip and fp.suffix.lower() == ".py":
        try:
            content = strip_python_explanations(content)
        except Exception:
            pass  # fallback to original content
    return content


# ════════════════════════════════════════════════════════════════════
#  TREE RENDERING
# ════════════════════════════════════════════════════════════════════

def build_tree(
    root: Path,
    files: list[Path],
    sizes: bool = False,
) -> str:
    """Build a visual ASCII tree string from a flat list of files.

    The output mimics ``tree(1)`` with proper branch characters
    (``├──`` / ``└──``) so the resulting text is unambiguous when pasted
    into an LLM context window.
    """
    root = root.resolve()
    lines: list[str] = [f"📦 {root.name}/"]

    rels: list[Path] = sorted(f.relative_to(root) for f in files)
    if not rels:
        return lines[0]

    from collections import defaultdict

    children_map: dict[str, list[tuple[str, bool]]] = defaultdict(list)

    all_dirs: set[str] = set()
    for r in rels:
        for parent in r.parents:
            pstr = str(parent)
            if pstr != ".":
                all_dirs.add(pstr)

    # Register directory entries
    _registered_dirs: set[tuple[str, str]] = set()
    for d in sorted(all_dirs):
        dp = Path(d)
        parent_key = str(dp.parent) if str(dp.parent) != "." else ""
        entry = (parent_key, dp.name)
        if entry not in _registered_dirs:
            _registered_dirs.add(entry)
            children_map[parent_key].append((dp.name, True))

    # Register file entries
    file_size_map: dict[str, int] = {}
    for r in rels:
        parent_key = str(r.parent) if str(r.parent) != "." else ""
        children_map[parent_key].append((r.name, False))
        if sizes:
            full = root / r
            try:
                file_size_map[str(r)] = full.stat().st_size
            except OSError:
                file_size_map[str(r)] = 0

    # Sort: directories first (alpha), then files (alpha)
    for key in children_map:
        children_map[key].sort(key=lambda x: (not x[1], x[0].lower()))

    # Deduplicate
    for key in children_map:
        seen: list[tuple[str, bool]] = []
        seen_set: set[tuple[str, bool]] = set()
        for item in children_map[key]:
            if item not in seen_set:
                seen.append(item)
                seen_set.add(item)
        children_map[key] = seen

    # Recursive render
    def _render(parent_key: str, prefix: str) -> None:
        items = children_map.get(parent_key, [])
        for idx, (name, is_dir) in enumerate(items):
            is_last: bool = idx == len(items) - 1
            connector: str = "└── " if is_last else "├── "
            child_prefix: str = prefix + ("    " if is_last else "│   ")

            if is_dir:
                lines.append(f"{prefix}{connector}📂 {name}/")
                child_key: str = (
                    f"{parent_key}/{name}" if parent_key else name
                )
                _render(child_key, child_prefix)
            else:
                suffix: str = ""
                if sizes:
                    rel_str: str = (
                        f"{parent_key}/{name}" if parent_key else name
                    )
                    sz: int = file_size_map.get(rel_str, 0)
                    suffix = f"  ({fmt_size(sz)})"
                lines.append(f"{prefix}{connector}📄 {name}{suffix}")

    _render("", "")

    return "\n".join(lines)


# ════════════════════════════════════════════════════════════════════
#  OUTPUT ASSEMBLY
# ════════════════════════════════════════════════════════════════════

def assemble_context(
    root: Path,
    files: list[Path],
    mode: str = "all",
    show_tree: bool = True,
    max_chars: int = 90_000,
    strip_explanations: bool = False,
) -> list[str]:
    """Build the final context string(s) ready for file write / clipboard.

    Parameters
    ----------
    root
        Project root.
    files
        Absolute paths of selected files.
    mode
        Tag shown in header (``all``, ``pick``, ``preset:name``, …).
    show_tree
        Whether to include the ASCII tree section.
    max_chars
        Maximum character count per part before splitting.
    strip_explanations
        If *True*, run AST comment killer on ``.py`` files.

    Returns
    -------
    list[str]
        One or more text chunks.  Usually one unless the context exceeds
        *max_chars*.
    """
    if not files:
        return []

    root = root.resolve()
    total: int = len(files)
    now: datetime = datetime.now()

    # ── individual file blocks ──
    blocks: list[str] = []
    for i, fp in enumerate(files, 1):
        rel: str = str(fp.relative_to(root)).replace("\\", "/")
        content: str = read_file_content(fp, strip=strip_explanations)
        if not content.endswith("\n"):
            content += "\n"
        blocks.append(
            f"┌─── 📄 [{i}/{total}] {rel}\n"
            f"{content}"
            f"└{'─' * 40}\n\n"
        )

    # ── tree section ──
    tree_section: str = ""
    if show_tree:
        tbody: str = build_tree(root, files)
        tree_section = (
            f"┌{'─' * 12}\n"
            f"│ 🗂️  STRUCTURE\n"
            f"├{'─' * 12}\n"
        )
        for line in tbody.split("\n"):
            tree_section += f"│ {line}\n"
        tree_section += f"└{'─' * 12}\n\n"

    # ── header / continuation / footer builders ──
    def _header(part: int | None = None, total_parts: int | None = None) -> str:
        tag: str = ""
        if part is not None and total_parts is not None and total_parts > 1:
            tag = f" ({part}/{total_parts})"
        return (
            f"{'═' * 14}\n"
            f"📋 {root.name} [{mode}]{tag}\n"
            f"📅 {now:%d.%m.%Y %H:%M:%S}\n"
            f"📄 Files: {total}\n"
            f"{'═' * 14}\n\n"
        )

    def _continuation(part: int, total_parts: int) -> str:
        return (
            f"{'═' * 5}\n"
            f"📋 {root.name} ({part}/{total_parts})\n"
            f"↳ continued\n"
            f"{'═' * 5}\n\n"
        )

    def _footer(part: int, total_parts: int, is_last: bool) -> str:
        if is_last:
            return f"{'═' * 5}\n✅ End\n{'═' * 5}\n"
        return f"{'═' * 5}\n➡️ Part {part + 1}/{total_parts}\n{'═' * 5}\n"

    # ── splitting into parts ──
    initial: str = _header() + tree_section
    raw_parts: list[str] = []
    current: str = initial
    first: bool = True

    for block in blocks:
        if len(current) + len(block) > max_chars and current != initial:
            raw_parts.append(current)
            current = ""
            first = False
        if not current:
            current = initial if first else ""
        current += block

    if current:
        raw_parts.append(current)

    # ── fix headers & footers ──
    tp: int = len(raw_parts)
    final: list[str] = []
    for idx, part in enumerate(raw_parts):
        if idx == 0 and tp > 1:
            part = part.replace(_header(), _header(1, tp), 1)
        elif idx > 0:
            part = _continuation(idx + 1, tp) + part
        part += _footer(idx + 1, tp, idx == tp - 1)
        final.append(part)

    return final


def write_output(
    root: Path,
    files: list[Path],
    output: str,
    mode: str = "panel",
    show_tree: bool = True,
    max_chars: int = 90_000,
    strip_explanations: bool = False,
) -> list[tuple[Path, int]]:
    """Assemble context and write to file(s).

    Returns ``[(path, char_count)]``.
    """
    parts: list[str] = assemble_context(
        root, files, mode, show_tree, max_chars, strip_explanations,
    )
    if not parts:
        return []

    out_path = Path(output)
    stem: str = out_path.stem
    suffix: str = out_path.suffix or ".txt"
    created: list[tuple[Path, int]] = []

    for idx, content in enumerate(parts):
        if len(parts) == 1:
            fn = out_path
        else:
            fn = out_path.parent / f"{stem}_p{idx + 1}{suffix}"
        fn.parent.mkdir(parents=True, exist_ok=True)
        fn.write_text(content, encoding="utf-8")
        created.append((fn, len(content)))

    return created