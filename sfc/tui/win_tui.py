"""Windows TUI engine using msvcrt + ANSI VT100 escape sequences.

v4.0.1 fixes:
  - Boxed header with display-width-aware padding (no right-border drift)
  - Entire panel dynamically centered in the terminal
  - All emoji measured via ``display_width()`` from ``base.py``
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import msvcrt
import os
import sys

from .base import (
    Engine,
    Key,
    KeyEvent,
    MenuItem,
    FOOTER_TEXT,
    PANEL_MAX_INNER,
    display_width,
    pad_right,
    truncate_to_width,
)


_ENABLE_VIRTUAL_TERMINAL_PROCESSING: int = 0x0004
_ENABLE_PROCESSED_OUTPUT: int = 0x0001
_STD_OUTPUT_HANDLE: int = -11

_kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]


def _enable_ansi() -> None:
    handle = _kernel32.GetStdHandle(_STD_OUTPUT_HANDLE)
    mode = ctypes.wintypes.DWORD()
    _kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    _kernel32.SetConsoleMode(
        handle,
        mode.value
        | _ENABLE_VIRTUAL_TERMINAL_PROCESSING
        | _ENABLE_PROCESSED_OUTPUT,
    )


_E = "\033["
_RST = f"{_E}0m"
_BOLD = f"{_E}1m"
_DIM = f"{_E}2m"
_FG_BLACK = f"{_E}30m"
_FG_GREEN = f"{_E}32m"
_FG_YELLOW = f"{_E}33m"
_FG_CYAN = f"{_E}36m"
_BG_CYAN = f"{_E}46m"
_CLS = f"{_E}2J{_E}H"
_HIDE = f"{_E}?25l"
_SHOW = f"{_E}?25h"
_CLR = f"{_E}2K"


def _mv(r: int, c: int) -> str:
    return f"{_E}{r + 1};{c + 1}H"


class WinEngine(Engine):

    def __init__(self) -> None:
        self._started: bool = False
        self._margin: int = 0
        self._panel_w: int = 58
        self._inner_w: int = 56
        self._header_end: int = 0

    # ════════════════════════════════════════════════════════════════
    #  LAYOUT
    # ════════════════════════════════════════════════════════════════

    def _calc_layout(self) -> None:
        _, cols = self.get_size()
        self._inner_w = min(cols - 4, PANEL_MAX_INNER)
        self._panel_w = self._inner_w + 2
        self._margin = max(0, (cols - self._panel_w) // 2)

    # ════════════════════════════════════════════════════════════════
    #  BOX HELPER
    # ════════════════════════════════════════════════════════════════

    def _box_line(
        self,
        left: str,
        fill: str,
        right: str,
        content: str,
    ) -> str:
        """Build a single box row string with correct display-width padding."""
        iw = self._inner_w
        if content == "":
            return left + fill * iw + right
        content = truncate_to_width(content, iw)
        content = pad_right(content, iw)
        return left + content + right

    # ════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════════

    def start(self) -> None:
        if self._started:
            return
        _enable_ansi()
        self._w(_HIDE)
        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._w(_SHOW + _RST)
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
                ext = msvcrt.getwch()
            except KeyboardInterrupt:
                return KeyEvent(Key.ESCAPE)
            return self._map_ext(ext)
        o = ord(ch)
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
            "H": Key.UP, "P": Key.DOWN, "K": Key.LEFT, "M": Key.RIGHT,
            "G": Key.HOME, "O": Key.END, "I": Key.PAGE_UP,
            "Q": Key.PAGE_DOWN, "S": Key.DELETE,
        }
        return KeyEvent(_MAP.get(ch, Key.UNKNOWN))

    def prompt(self, label: str, prefill: str = "") -> str | None:
        rows, cols = self.get_size()
        pr = rows - 3
        buf: list[str] = list(prefill)
        self._w(_SHOW)
        while True:
            disp = "".join(buf)
            mx = cols - len(label) - 3
            if len(disp) > mx:
                disp = disp[-mx:]
            self._w(
                _mv(pr, 0) + _CLR + f" {_FG_YELLOW}{label}{_RST}{disp}"
            )
            ev = self.get_key()
            if ev.key is Key.ESCAPE:
                self._w(_HIDE)
                return None
            if ev.key is Key.ENTER:
                self._w(_HIDE)
                return "".join(buf)
            if ev.key is Key.BACKSPACE:
                if buf:
                    buf.pop()
            elif ev.is_printable:
                buf.append(ev.char)

    def confirm(self, question: str) -> bool:
        rows, cols = self.get_size()
        pr = rows - 3
        full = f"{question} (y/n): "
        self._w(_mv(pr, 0) + _CLR + f" {_FG_YELLOW}{full}{_RST}")
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
        self._calc_layout()
        rows, _ = self.get_size()
        row = 0
        mg = self._margin
        out: list[str] = []

        # ── Title box (cyan bold) ──
        if len(lines) >= 1 and lines[0].strip():
            txt = f" {lines[0].strip()} "
            top = self._box_line("╔", "═", "╗", "")
            mid = self._box_line("║", " ", "║", txt)
            bot = self._box_line("╚", "═", "╝", "")
            for s in (top, mid, bot):
                out.append(
                    _mv(row, mg) + _CLR + f"{_BOLD}{_FG_CYAN}{s}{_RST}"
                )
                row += 1

        # ── Stats box (dim) ──
        if len(lines) >= 2 and lines[1].strip():
            txt = f" {lines[1].strip()} "
            top = self._box_line("┌", "─", "┐", "")
            mid = self._box_line("│", " ", "│", txt)
            bot = self._box_line("└", "─", "┘", "")
            for s in (top, mid, bot):
                out.append(
                    _mv(row, mg) + _CLR + f"{_DIM}{s}{_RST}"
                )
                row += 1

        # ── Extra lines ──
        for i in range(2, len(lines)):
            if row >= rows - 4:
                break
            if lines[i].strip():
                out.append(
                    _mv(row, mg) + _CLR + f"{_DIM}{lines[i]}{_RST}"
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
        self._calc_layout()
        rows, _ = self.get_size()
        start = self._header_end
        mg = self._margin
        pw = self._panel_w
        out: list[str] = []

        for vi in range(visible_count):
            idx = offset + vi
            row = start + vi
            if row >= rows - 3:
                break
            if idx >= len(items):
                out.append(_mv(row, 0) + _CLR)
                continue

            item = items[idx]
            is_cur = idx == cursor

            # ── Prefix ──
            if item.checked is not None:
                mark = "✓" if item.checked else " "
                prefix = f" [{mark}] "
            else:
                prefix = "   "
            if is_cur:
                prefix = " ▸" + prefix[2:]

            label = item.label
            suffix = f"  {item.suffix}" if item.suffix else ""

            # ── Width-aware truncation ──
            pw_dw = display_width(prefix)
            sw_dw = display_width(suffix)
            max_label = pw - pw_dw - sw_dw - 1
            if display_width(label) > max_label:
                label = truncate_to_width(label, max(0, max_label - 1)) + "…"

            line = f"{prefix}{label}{suffix}"
            line = truncate_to_width(line, pw)

            if is_cur:
                styled = f"{_BG_CYAN}{_FG_BLACK}{_BOLD}{line}{_RST}"
            elif not item.enabled:
                styled = f"{_DIM}{line}{_RST}"
            elif item.checked:
                styled = f"{_FG_GREEN}{line}{_RST}"
            else:
                styled = line

            out.append(_mv(row, mg) + _CLR + styled)

        # ── Scroll indicators ──
        ind_col = mg + pw - 1
        if offset > 0:
            out.append(_mv(start, ind_col) + f"{_DIM}▲{_RST}")
        if offset + visible_count < len(items):
            last = start + min(visible_count, len(items) - offset) - 1
            if last < rows - 3:
                out.append(_mv(last, ind_col) + f"{_DIM}▼{_RST}")

        self._w("".join(out))

    def draw_footer(self, lines: list[str]) -> None:
        self._calc_layout()
        rows, _ = self.get_size()
        total = len(lines)
        start_row = rows - total - 1
        mg = self._margin
        out: list[str] = []

        for i, line in enumerate(lines):
            row = start_row + i
            if row < 0 or row >= rows:
                continue
            if i == total - 1:
                out.append(
                    _mv(row, 0) + _CLR
                    + _mv(row, mg)
                    + f"{_FG_CYAN}{line}{_RST}"
                )
            else:
                out.append(
                    _mv(row, 0) + _CLR
                    + _mv(row, mg)
                    + f"{_FG_YELLOW}{line}{_RST}"
                )
        self._w("".join(out))

    def draw_text_block(self, text: str) -> None:
        text_lines = text.split("\n")
        offset = 0
        while True:
            rows, cols = self.get_size()
            visible = rows - 3
            out: list[str] = [_CLS]
            for i in range(visible):
                li = offset + i
                if li >= len(text_lines):
                    break
                out.append(
                    _mv(i, 0)
                    + truncate_to_width(text_lines[li], cols - 1)
                )
            tp = max(1, (len(text_lines) + visible - 1) // visible)
            cp = (offset // visible) + 1 if visible > 0 else 1
            hint = f" ↑↓:scroll  q/ESC:back  ({cp}/{tp})"
            out.append(_mv(rows - 2, 0) + f"{_FG_YELLOW}{hint}{_RST}")
            out.append(_mv(rows - 1, 1) + f"{_FG_CYAN}{FOOTER_TEXT}{_RST}")
            self._w("".join(out))
            ev = self.get_key()
            if ev.key is Key.ESCAPE or (
                ev.key is Key.CHAR and ev.char in ("q", "Q")
            ):
                return
            if ev.key is Key.UP:
                offset = max(0, offset - 1)
            elif ev.key is Key.DOWN:
                offset = min(max(0, len(text_lines) - visible), offset + 1)
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
            dw = display_width(line)
            x = max(0, (cols - dw) // 2)
            out.append(
                _mv(r, x) + f"{_BOLD}{_FG_CYAN}{line}{_RST}"
            )
        out.append(_mv(rows - 1, 1) + f"{_FG_CYAN}{FOOTER_TEXT}{_RST}")
        if wait:
            out.append(_mv(rows - 2, 1) + f"{_DIM}Press any key...{_RST}")
        self._w("".join(out))
        if wait:
            self.get_key()

    @staticmethod
    def _w(s: str) -> None:
        sys.stdout.write(s)
        sys.stdout.flush()