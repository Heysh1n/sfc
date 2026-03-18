# fc/tree.py
"""Project file-tree renderer."""

from pathlib import Path

from fc.utils import fmt_size


def build_tree(
    root: str | Path,
    files: list[Path],
    sizes: bool = False,
) -> str:
    """Build a visual tree string from a list of files."""
    root = Path(root) if not isinstance(root, Path) else root
    lines = [f"📦 {root.name}/"]
    rels = sorted(f.relative_to(root) for f in files)

    # Collect directories
    dirs: set[Path] = set()
    for r in rels:
        for p in r.parents:
            if str(p) != ".":
                dirs.add(p)

    file_map = {f.relative_to(root): f for f in files} if sizes else {}

    # Merge dirs + files, sort
    items: list[tuple[Path, str]] = [(d, "dir") for d in dirs] + [(r, "file") for r in rels]
    items.sort(key=lambda x: (x[0].parts, x[1] == "file"))

    seen: set[str] = set()
    for path, typ in items:
        k = str(path)
        if k in seen:
            continue
        seen.add(k)

        indent = "│   " * (len(path.parts) - 1)

        if typ == "dir":
            lines.append(f"{indent}├── 📂 {path.name}/")
        else:
            sfx = ""
            if sizes and path in file_map and file_map[path].exists():
                sfx = f"  ({fmt_size(file_map[path].stat().st_size)})"
            lines.append(f"{indent}├── 📄 {path.name}{sfx}")

    return "\n".join(lines)