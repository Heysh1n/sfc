"""Entry point for ``python -m sfc`` and zipapp execution."""

from __future__ import annotations

import sys
import os


def main() -> None:
    # Zipapp flattens into zip root — relative imports break.
    # Detect and fix by inserting the zip/dir into sys.path so the
    # 'sfc' package inside the staging layout is importable.
    try:
        from .app import run
    except ImportError:
        # We are NOT inside a package (zipapp direct execution).
        # The zipapp was built with staging/ containing sfc/ as subdir.
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in sys.path:
            sys.path.insert(0, _here)
        from sfc.app import run  # type: ignore[no-redef]

    try:
        run(sys.argv[1:])
    except Exception as exc:
        print(f"\n❌ Fatal error: {exc}", file=sys.stderr)
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()