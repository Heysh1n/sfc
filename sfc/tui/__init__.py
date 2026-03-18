"""TUI engine factory — returns the right backend for the current OS."""

from __future__ import annotations

import os
import sys
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .base import Engine


def get_engine() -> Engine:
    """Instantiate and return the platform-appropriate TUI engine.

    - Windows → :class:`WinEngine` (msvcrt + ctypes console API)
    - POSIX   → :class:`CursesEngine` (stdlib curses)

    Raises
    ------
    RuntimeError
        If no usable backend can be initialised.
    """
    if os.name == "nt":
        from .win_tui import WinEngine
        return WinEngine()

    # POSIX: curses requires a real terminal
    if not (hasattr(sys.stdout, "isatty") and sys.stdout.isatty()):
        raise RuntimeError(
            "sfc interactive mode requires a terminal (stdout is not a TTY)"
        )

    from .curses_tui import CursesEngine
    return CursesEngine()