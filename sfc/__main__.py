"""Entry point for ``python -m sfc`` and zipapp execution."""

from __future__ import annotations

import sys
import os


def main() -> None:
    """Bootstrap and run sfc."""
    try:
        from .app import run
    except ImportError:
        # Zipapp direct execution — relative imports unavailable.
        # The zipapp staging layout has sfc/ as a subdirectory.
        _here = os.path.dirname(os.path.abspath(__file__))
        if _here not in sys.path:
            sys.path.insert(0, _here)
        from sfc.app import run  # type: ignore[no-redef]

    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        print("\n👋 Interrupted", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\n❌ Fatal error: {exc}", file=sys.stderr)
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()