"""Windows TUI engine using msvcrt + ctypes Console API.

Provides the same interface as :class:`CursesEngine` but works natively
on Windows without curses (which is not bundled on Windows Python).

Uses:
- ``msvcrt.getwch()`` for keyboard input
- ``ctypes`` calls to ``kernel32`` for console buffer manipulation
- Direct ``sys.stdout.write`` with ANSI escapes (Windows 10+ supports
  Virtual Terminal Sequences when enabled).
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import msvcrt
import os
import sys
from typing import TYPE_CHECKING

from .base import Engine, Key, KeyEvent, MenuItem

if TYPE_CHECKING:
    pass


# ── Win32 constants ─────────────────────────────────────────────────

_ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004
_ENABLE_PROCESSED_OUTPUT: int = 0x0001
_STD_OUTPUT_HANDLE: int = -11
_STD_INPUT_HANDLE: int = -10

_kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]


def _enable_ansi() -> None:
    """Enable ANSI/VT100 escape sequences on Windows 10+."""
    handle = _kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
    mode = ctypes.wintypes.DWORD()
    _kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    _kernel32.SetConsoleMode(
        handle, mode.value | _ENABLE_VIRTUAL_TERMINAL_PROCESSING | _ENABLE_PROCESSED_OUTPUT,
    )


# ── ANSI helpers ────────────────────────────────────────────────────

_ESC: str = "\033["

_RESET: str = f"{_ESC}0m"
_BOLD: str = f"{_ESC}1m"
_DIM: str = f"{_ESC}2m"
_FG_CYAN: str = f"{_ESC}36m"
_FG_GREEN: str = f"{_ESC}32m"
_FG_YELLOW: str = f"{_ESC}33m"
_FG_RED: str = f"{_ESC}31m"
_FG_WHITE: str = f"{_ESC}37m"
_BG_CYAN: str = f"{_ESC}46m"
_FG_BLACK: str = f"{_ESC}30m"
_CLEAR_SCREEN: str = f"{_ESC}2J{_ESC}H"
_HIDE_CURSOR: str = f"{_ESC}?25l"
_SHOW_CURSOR: str = f"{_ESC}?25h"
_CLEAR_LINE: str = f"{_ESC}2K"


def _move(row: int, col: int) -> str:
    return f"{_ESC}{row + 1};{col + 1}H"


class WinEngine(Engine):
    """Concrete TUI engine for Windows using msvcrt + ANSI escapes."""

    def __init__(self) -> None:
        self._started: bool = False

    # ════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════════

    def start(self) -> None:
        if self._started:
            return
        _enable_ansi()
        self._write(_HIDE_CURSOR)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._write(_SHOW_CURSOR + _RESET)
        self._started = False

    # ════════════════════════════════════════════════════════════════
    #  INPUT
    # ════════════════════════════════════════════════════════════════

    def get_key(self) -> KeyEvent:
        try:
            ch: str = msvcrt.getwch()
        except KeyboardInterrupt:
            return KeyEvent(Key.ESCAPE)

        # Special keys: first char is \x00 or \xe0
        if ch in ("\x00", "\xe0"):
            try:
                ext: str = msvcrt.getwch()
            except KeyboardInterrupt:
                return KeyEvent(Key.ESCAPE)
            return self._map_extended(ext)

        o: int = ord(ch)
        if o == 27:
            return KeyEvent(Key.ESCAPE)
        if o == 13:
            return KeyEvent(Key.ENTER)
        if o == 32:
            return KeyEvent(Key.SPACE)
        if o == 9:
            return KeyEvent(Key.TAB)
        if o == 8:
            return KeyEvent(Key.BACKSPACE)
        if 32 <= o < 127 or o > 127:
            return KeyEvent(Key.CHAR, ch)
        return KeyEvent(Key.UNKNOWN)

    @staticmethod
    def _map_extended(ch: str) -> KeyEvent:
        _MAP: dict[str, Key] = {
            "H": Key.UP,
            "P": Key.DOWN,
            "K": Key.LEFT,
            "M": Key.RIGHT,
            "G": Key.HOME,
            "O": Key.END,
            "I": Key.PAGE_UP,
            "Q": Key.PAGE_DOWN,
            "S": Key.DELETE,
        }
        key = _MAP.get(ch, Key.UNKNOWN)
        return KeyEvent(key)

    def prompt(self, label: str, prefill: str = "") -> str | None:
        rows, cols = self.get_size()
        prompt_row: int = rows - 2
        buf: list[str] = list(prefill)

        self._write(_SHOW_CURSOR)

        while True:
            # Draw prompt line
            display: str = "".join(buf)
            max_d: int = cols - len(label) - 3
            if len(display) > max_d:
                display = display[-max_d:]
            line: str = f"{_FG_YELLOW}{label}{_RESET}{display}"
            self._write(
                _move(prompt_row, 0) + _CLEAR_LINE + " " + line
            )

            ev = self.get_key()
            if ev.key is Key.ESCAPE:
                self._write(_HIDE_CURSOR)
                return None
            if ev.key is Key.ENTER:
                self._write(_HIDE_CURSOR)
                return "".join(buf)
            if ev.key is Key.BACKSPACE:
                if buf:
                    buf.pop()
            elif ev.is_printable:
                buf.append(ev.char)

    def confirm(self, question: str) -> bool:
        rows, cols = self.get_size()
        prompt_row = rows - 2
        full = f"{question} (y/n): "
        self._write(
            _move(prompt_row, 0) + _CLEAR_LINE + f" {_FG_YELLOW}{full}{_RESET}"
        )
        while True:
            ev = self.get_key()
            if ev.key is Key.CHAR and ev.char.lower() in ("y", "n", "д", "н"):
                return ev.char.lower() in ("y", "д")
            if ev.key in (Key.ENTER, Key.ESCAPE):
                return False

    # ════════════════════════════════════════════════════════════════
    #  RENDERING
    # ════════════════════════════════════════════════════════════════

    def clear(self) -> None:
        self._write(_CLEAR_SCREEN)

    def get_size(self) -> tuple[int, int]:
        try:
            ts = os.get_terminal_size()
            return (ts.lines, ts.columns)
        except OSError:
            return (25, 80)

    def draw_header(self, lines: list[str]) -> None:
        rows, cols = self.get_size()
        out: list[str] = []
        for i, line in enumerate(lines):
            if i >= rows - 2:
                break
            out.append(
                _move(i, 0) + _CLEAR_LINE + f"{_BOLD}{_FG_CYAN}{line[:cols - 1]}{_RESET}"
            )
        # Separator
        sep_row = len(lines)
        if sep_row < rows - 1:
            sep = "─" * min(cols - 1, 60)
            out.append(_move(sep_row, 0) + _CLEAR_LINE + f"{_DIM}{sep}{_RESET}")
        self._write("".join(out))

    def draw_items(
        self,
        items: list[MenuItem],
        cursor: int,
        offset: int,
        visible_count: int,
    ) -> None:
        rows, cols = self.get_size()
        start_row: int = self._find_item_start_row_win()
        out: list[str] = []

        for vi in range(visible_count):
            idx: int = offset + vi
            row: int = start_row + vi
            if row >= rows - 2:
                break
            if idx >= len(items):
                # Clear remaining visible rows
                out.append(_move(row, 0) + _CLEAR_LINE)
                continue

            item: MenuItem = items[idx]
            is_cur: bool = idx == cursor

            prefix: str
            if item.checked is not None:
                mark: str = "✓" if item.checked else " "
                prefix = f" [{mark}] "
            else:
                prefix = "  "

            if is_cur:
                prefix = " ▸" + prefix[2:]

            label: str = item.label
            suffix: str = f"  {item.suffix}" if item.suffix else ""

            max_label: int = cols - len(prefix) - len(suffix) - 2
            if len(label) > max_label:
                label = label[:max(0, max_label - 1)] + "…"

            line: str = f"{prefix}{label}{suffix}"
            line = line[:cols - 1]

            if is_cur:
                styled = f"{_BG_CYAN}{_FG_BLACK}{_BOLD}{line}{_RESET}"
            elif not item.enabled:
                styled = f"{_DIM}{line}{_RESET}"
            elif item.checked:
                styled = f"{_FG_GREEN}{line}{_RESET}"
            else:
                styled = line

            out.append(_move(row, 0) + _CLEAR_LINE + styled)

        # Scroll indicators
        if offset > 0:
            out.append(_move(start_row, cols - 2) + f"{_DIM}▲{_RESET}")
        if offset + visible_count < len(items):
            last_row = start_row + min(visible_count, len(items) - offset) - 1
            if last_row < rows - 2:
                out.append(_move(last_row, cols - 2) + f"{_DIM}▼{_RESET}")

        self._write("".join(out))

    def draw_footer(self, lines: list[str]) -> None:
        rows, cols = self.get_size()
        out: list[str] = []
        for i, line in enumerate(lines):
            row = rows - len(lines) + i
            if row < 0:
                continue
            out.append(
                _move(row, 0) + _CLEAR_LINE + f" {_FG_YELLOW}{line[:cols - 2]}{_RESET}"
            )
        self._write("".join(out))

    def draw_text_block(self, text: str) -> None:
        text_lines: list[str] = text.split("\n")
        offset: int = 0

        while True:
            rows, cols = self.get_size()
            visible = rows - 2
            out: list[str] = [_CLEAR_SCREEN]

            for i in range(visible):
                li = offset + i
                if li >= len(text_lines):
                    break
                line = text_lines[li][:cols - 1]
                out.append(_move(i, 0) + line)

            total_pages = max(1, (len(text_lines) + visible - 1) // visible)
            cur_page = (offset // visible) + 1 if visible > 0 else 1
            hint = f" ↑↓:scroll  q/ESC:back  ({cur_page}/{total_pages})"
            out.append(_move(rows - 1, 0) + f"{_FG_YELLOW}{hint[:cols - 1]}{_RESET}")
            self._write("".join(out))

            ev = self.get_key()
            if ev.key is Key.ESCAPE or (ev.key is Key.CHAR and ev.char in ("q", "Q")):
                return
            if ev.key is Key.UP:
                offset = max(0, offset - 1)
            elif ev.key is Key.DOWN:
                offset = min(max(0, len(text_lines) - visible), offset + 1)
            elif ev.key is Key.PAGE_UP:
                offset = max(0, offset - visible)
            elif ev.key is Key.PAGE_DOWN:
                offset = min(max(0, len(text_lines) - visible), offset + visible)
            elif ev.key is Key.HOME:
                offset = 0
            elif ev.key is Key.END:
                offset = max(0, len(text_lines) - visible)

    def show_message(self, msg: str, wait: bool = True) -> None:
        rows, cols = self.get_size()
        lines = msg.split("\n")
        start_row = max(0, (rows - len(lines)) // 2)
        out: list[str] = [_CLEAR_SCREEN]
        for i, line in enumerate(lines):
            r = start_row + i
            if r >= rows:
                break
            x = max(0, (cols - len(line)) // 2)
            out.append(_move(r, x) + f"{_BOLD}{_FG_CYAN}{line[:cols - 1]}{_RESET}")
        if wait:
            out.append(_move(rows - 1, 1) + f"{_DIM}Press any key...{_RESET}")
        self._write("".join(out))
        if wait:
            self.get_key()

    # ════════════════════════════════════════════════════════════════
    #  INTERNAL HELPERS
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _write(s: str) -> None:
        sys.stdout.write(s)
        sys.stdout.flush()

    @staticmethod
    def _find_item_start_row_win() -> int:
        """Header is typically 3–4 lines + 1 separator."""
        return 4