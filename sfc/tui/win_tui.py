"""Windows TUI engine using msvcrt + ANSI VT100 escape sequences.

v4.0 layout (boxed header):
  ╔══════════════════════════════════════════════╗
  ║  🔧 Smart File Collector v4.0.0             ║  (cyan bold)
  ╚══════════════════════════════════════════════╝
  ┌──────────────────────────────────────────────┐
  │  📂 Project: sfc  │  📄 Files: 19           │  (dim/gray)
  └──────────────────────────────────────────────┘
  Menu items...
  ↑↓:navigate  ENTER:select  q:quit              (yellow)
  Made with ❤️ by Heysh1n                          (cyan)
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import msvcrt
import os
import sys

from .base import Engine, Key, KeyEvent, MenuItem
from ..version import FOOTER_TEXT


# ── Win32 constants ─────────────────────────────────────────────────

_ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004
_ENABLE_PROCESSED_OUTPUT: int = 0x0001
_STD_OUTPUT_HANDLE: int = -11

_kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]


def _enable_ansi() -> None:
    """Enable ANSI/VT100 escape sequences on Windows 10+."""
    handle = _kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
    mode = ctypes.wintypes.DWORD()
    _kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    _kernel32.SetConsoleMode(
        handle,
        mode.value
        | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
        | _ENABLE_PROCESSED_OUTPUT,
    )


# ── ANSI helpers ────────────────────────────────────────────────────

_E = "\033["

_RST = f"{_E}0m"
_BOLD = f"{_E}1m"
_DIM = f"{_E}2m"
_FG_BLACK = f"{_E}30m"
_FG_GREEN = f"{_E}32m"
_FG_YELLOW = f"{_E}33m"
_FG_WHITE = f"{_E}37m"
_FG_CYAN = f"{_E}36m"
_BG_CYAN = f"{_E}46m"
_CLS = f"{_E}2J{_E}H"
_HIDE_CUR = f"{_E}?25l"
_SHOW_CUR = f"{_E}?25h"
_CLR_LINE = f"{_E}2K"


def _mv(row: int, col: int) -> str:
    return f"{_E}{row + 1};{col + 1}H"


class WinEngine(Engine):
    """Concrete TUI engine for Windows using msvcrt + ANSI escapes."""

    def __init__(self) -> None:
        self._started: bool = False
        self._header_end: int = 0

    # ════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════════

    def start(self) -> None:
        if self._started:
            return
        _enable_ansi()
        self._w(_HIDE_CUR)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._w(_SHOW_CUR + _RST)
        self._started = False

    # ════════════════════════════════════════════════════════════════
    #  INPUT
    # ════════════════════════════════════════════════════════════════

    def get_key(self) -> KeyEvent:
        try:
            ch: str = msvcrt.getwch()
        except KeyboardInterrupt:
            return KeyEvent(Key.ESCAPE)

        if ch in ("\x00", "\xe0"):
            try:
                ext: str = msvcrt.getwch()
            except KeyboardInterrupt:
                return KeyEvent(Key.ESCAPE)
            return self._map_ext(ext)

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
    def _map_ext(ch: str) -> KeyEvent:
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
        return KeyEvent(_MAP.get(ch, Key.UNKNOWN))

    def prompt(self, label: str, prefill: str = "") -> str | None:
        rows, cols = self.get_size()
        prompt_row: int = rows - 3
        buf: list[str] = list(prefill)

        self._w(_SHOW_CUR)

        while True:
            display: str = "".join(buf)
            max_d: int = cols - len(label) - 3
            if len(display) > max_d:
                display = display[-max_d:]
            self._w(
                _mv(prompt_row, 0)
                + _CLR_LINE
                + f" {_FG_YELLOW}{label}{_RST}{display}"
            )

            ev = self.get_key()
            if ev.key is Key.ESCAPE:
                self._w(_HIDE_CUR)
                return None
            if ev.key is Key.ENTER:
                self._w(_HIDE_CUR)
                return "".join(buf)
            if ev.key is Key.BACKSPACE:
                if buf:
                    buf.pop()
            elif ev.is_printable:
                buf.append(ev.char)

    def confirm(self, question: str) -> bool:
        rows, cols = self.get_size()
        prompt_row = rows - 3
        full = f"{question} (y/n): "
        self._w(
            _mv(prompt_row, 0)
            + _CLR_LINE
            + f" {_FG_YELLOW}{full}{_RST}"
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
        self._w(_CLS)

    def get_size(self) -> tuple[int, int]:
        try:
            ts = os.get_terminal_size()
            return (ts.lines, ts.columns)
        except OSError:
            return (25, 80)

    def draw_header(self, lines: list[str]) -> None:
        """Render header with boxed title (cyan) and boxed stats (gray).

        Convention:
          lines[0] → title text → ╔═══╗ cyan bold box
          lines[1] → stats text → ┌───┐ dim/gray box
          lines[2:] → additional plain dim lines
        """
        rows, cols = self.get_size()
        box_w: int = min(cols - 4, 56)
        row: int = 0
        out: list[str] = []

        # ── Title box (cyan bold) ──
        if len(lines) >= 1 and lines[0].strip():
            title_text = lines[0].strip()
            padded = f" {title_text} ".ljust(box_w)[:box_w]
            top = "╔" + "═" * box_w + "╗"
            mid = "║" + padded + "║"
            bot = "╚" + "═" * box_w + "╝"
            out.append(
                _mv(row, 1) + _CLR_LINE + f"{_BOLD}{_FG_CYAN}{top}{_RST}"
            )
            row += 1
            out.append(
                _mv(row, 1) + _CLR_LINE + f"{_BOLD}{_FG_CYAN}{mid}{_RST}"
            )
            row += 1
            out.append(
                _mv(row, 1) + _CLR_LINE + f"{_BOLD}{_FG_CYAN}{bot}{_RST}"
            )
            row += 1

        # ── Stats box (dim/gray) ──
        if len(lines) >= 2 and lines[1].strip():
            stats_text = lines[1].strip()
            padded = f" {stats_text} ".ljust(box_w)[:box_w]
            top = "┌" + "─" * box_w + "┐"
            mid = "│" + padded + "│"
            bot = "└" + "─" * box_w + "┘"
            out.append(
                _mv(row, 1) + _CLR_LINE + f"{_DIM}{top}{_RST}"
            )
            row += 1
            out.append(
                _mv(row, 1) + _CLR_LINE + f"{_DIM}{mid}{_RST}"
            )
            row += 1
            out.append(
                _mv(row, 1) + _CLR_LINE + f"{_DIM}{bot}{_RST}"
            )
            row += 1

        # ── Additional lines (plain dim) ──
        for i in range(2, len(lines)):
            if row >= rows - 4:
                break
            if lines[i].strip():
                out.append(
                    _mv(row, 1) + _CLR_LINE
                    + f"{_DIM}{lines[i][:cols - 3]}{_RST}"
                )
                row += 1

        self._header_end = row
        self._w("".join(out))

    def draw_items(
        self,
        items: list[MenuItem],
        cursor: int,
        offset: int,
        visible_count: int,
    ) -> None:
        rows, cols = self.get_size()
        start_row: int = self._header_end
        out: list[str] = []

        for vi in range(visible_count):
            idx: int = offset + vi
            row: int = start_row + vi
            if row >= rows - 3:
                break
            if idx >= len(items):
                out.append(_mv(row, 0) + _CLR_LINE)
                continue

            item: MenuItem = items[idx]
            is_cur: bool = idx == cursor

            # Prefix
            prefix: str
            if item.checked is not None:
                mark: str = "✓" if item.checked else " "
                prefix = f" [{mark}] "
            else:
                prefix = "   "

            if is_cur:
                prefix = " ▸" + prefix[2:]

            label: str = item.label
            suffix: str = f"  {item.suffix}" if item.suffix else ""

            max_label: int = cols - len(prefix) - len(suffix) - 2
            if len(label) > max_label:
                label = label[: max(0, max_label - 1)] + "…"

            line: str = f"{prefix}{label}{suffix}"
            line = line[: cols - 1]

            if is_cur:
                styled = f"{_BG_CYAN}{_FG_BLACK}{_BOLD}{line}{_RST}"
            elif not item.enabled:
                styled = f"{_DIM}{line}{_RST}"
            elif item.checked:
                styled = f"{_FG_GREEN}{line}{_RST}"
            else:
                styled = line

            out.append(_mv(row, 0) + _CLR_LINE + styled)

        # Scroll indicators
        if offset > 0:
            out.append(
                _mv(start_row, cols - 2) + f"{_DIM}▲{_RST}"
            )
        if offset + visible_count < len(items):
            last_row = start_row + min(
                visible_count, len(items) - offset,
            ) - 1
            if last_row < rows - 3:
                out.append(
                    _mv(last_row, cols - 2) + f"{_DIM}▼{_RST}"
                )

        self._w("".join(out))

    def draw_footer(self, lines: list[str]) -> None:
        """Render footer: nav hints (yellow) + author line (cyan)."""
        rows, cols = self.get_size()
        total = len(lines)
        start_row = rows - total - 1

        out: list[str] = []
        for i, line in enumerate(lines):
            row = start_row + i
            if row < 0 or row >= rows:
                continue
            if i == total - 1:
                out.append(
                    _mv(row, 0) + _CLR_LINE
                    + f" {_FG_CYAN}{line[:cols - 2]}{_RST}"
                )
            else:
                out.append(
                    _mv(row, 0) + _CLR_LINE
                    + f" {_FG_YELLOW}{line[:cols - 2]}{_RST}"
                )
        self._w("".join(out))

    def draw_text_block(self, text: str) -> None:
        text_lines: list[str] = text.split("\n")
        offset: int = 0

        while True:
            rows, cols = self.get_size()
            visible = rows - 3
            out: list[str] = [_CLS]

            for i in range(visible):
                li = offset + i
                if li >= len(text_lines):
                    break
                out.append(_mv(i, 0) + text_lines[li][: cols - 1])

            total_pages = max(
                1, (len(text_lines) + visible - 1) // visible,
            )
            cur_page = (offset // visible) + 1 if visible > 0 else 1
            hint = f" ↑↓:scroll  q/ESC:back  ({cur_page}/{total_pages})"
            out.append(
                _mv(rows - 2, 0)
                + f"{_FG_YELLOW}{hint[:cols - 1]}{_RST}"
            )
            out.append(
                _mv(rows - 1, 0)
                + f" {_FG_CYAN}{FOOTER_TEXT[:cols - 2]}{_RST}"
            )
            self._w("".join(out))

            ev = self.get_key()
            if ev.key is Key.ESCAPE or (
                ev.key is Key.CHAR and ev.char in ("q", "Q")
            ):
                return
            if ev.key is Key.UP:
                offset = max(0, offset - 1)
            elif ev.key is Key.DOWN:
                offset = min(
                    max(0, len(text_lines) - visible), offset + 1,
                )
            elif ev.key is Key.PAGE_UP:
                offset = max(0, offset - visible)
            elif ev.key is Key.PAGE_DOWN:
                offset = min(
                    max(0, len(text_lines) - visible), offset + visible,
                )
            elif ev.key is Key.HOME:
                offset = 0
            elif ev.key is Key.END:
                offset = max(0, len(text_lines) - visible)

    def show_message(self, msg: str, wait: bool = True) -> None:
        rows, cols = self.get_size()
        lines = msg.split("\n")
        start_row = max(0, (rows - len(lines) - 2) // 2)
        out: list[str] = [_CLS]

        for i, line in enumerate(lines):
            r = start_row + i
            if r >= rows - 2:
                break
            x = max(0, (cols - len(line)) // 2)
            out.append(
                _mv(r, x)
                + f"{_BOLD}{_FG_CYAN}{line[:cols - 1]}{_RST}"
            )

        out.append(
            _mv(rows - 1, 0)
            + f" {_FG_CYAN}{FOOTER_TEXT[:cols - 2]}{_RST}"
        )

        if wait:
            out.append(
                _mv(rows - 2, 1)
                + f"{_DIM}Press any key...{_RST}"
            )
        self._w("".join(out))
        if wait:
            self.get_key()

    # ════════════════════════════════════════════════════════════════
    #  INTERNAL
    # ════════════════════════════════════════════════════════════════

    @staticmethod
    def _w(s: str) -> None:
        sys.stdout.write(s)
        sys.stdout.flush()