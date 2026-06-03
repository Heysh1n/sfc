"""Single entry point for ``python -m sfc`` and zipapp execution."""

from __future__ import annotations

import os
import sys
import types


def _ensure_package() -> None:
    """Expose archive-root modules as the ``sfc`` package when needed."""
    if __package__ == "sfc":
        return

    package_root = os.path.dirname(os.path.abspath(__file__))
    if "sfc" not in sys.modules:
        package = types.ModuleType("sfc")
        package.__file__ = os.path.join(package_root, "__init__.py")
        package.__package__ = "sfc"
        package.__path__ = [package_root]  # type: ignore[attr-defined]
        sys.modules["sfc"] = package


def main() -> None:
    """Run the CLI/TUI application."""
    _ensure_package()

    from sfc.app import run

    try:
        run(sys.argv[1:])
    except KeyboardInterrupt:
        print("\n[!] Stopped by user", file=sys.stderr)
        sys.exit(130)
    except Exception as exc:
        print(f"\nFatal error: {exc}", file=sys.stderr)
        if "--debug" in sys.argv:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
