"""Curses-based TUI engine for POSIX systems (Linux / macOS).

v4.0.1 fixes:
  - Boxed header with display-width-aware padding (no right-border drift)
  - Entire panel dynamically centered in the terminal
  - All emoji measured via ``display_width()`` from ``base.py``
"""

from __future__ import annotations

import curses
import locale
import os

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


_CP_NORMAL: int = 0
_CP_TITLE: int = 1
_CP_CURSOR: int = 2
_CP_CHECKED: int = 3
_CP_DIM: int = 4
_CP_NAV: int = 5
_CP_ERROR: int = 6
_CP_INPUT: int = 7
_CP_AUTHOR: int = 8


class CursesEngine(Engine):

    def __init__(self) -> None:
        self._scr: curses.window | None = None
        self._started: bool = False
        self._margin: int = 0
        self._panel_w: int = 58
        self._inner_w: int = 56
        self._header_end: int = 0

    # ════════════════════════════════════════════════════════════════
    #  LAYOUT
    # ════════════════════════════════════════════════════════════════

    def _calc_layout(self) -> None:
        """Recalculate centering margins based on current terminal size."""
        _, cols = self.get_size()
        self._inner_w = min(cols - 4, PANEL_MAX_INNER)
        self._panel_w = self._inner_w + 2  # box borders
        self._margin = max(0, (cols - self._panel_w) // 2)

    # ════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════════

    def start(self) -> None:
        if self._started:
            return
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass
        os.environ.setdefault("ESCDELAY", "25")

        self._scr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self._scr.keypad(True)

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(_CP_TITLE, curses.COLOR_CYAN, -1)
            curses.init_pair(_CP_CURSOR, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(_CP_CHECKED, curses.COLOR_GREEN, -1)
            curses.init_pair(_CP_DIM, curses.COLOR_WHITE, -1)
            curses.init_pair(_CP_NAV, curses.COLOR_YELLOW, -1)
            curses.init_pair(_CP_ERROR, curses.COLOR_RED, -1)
            curses.init_pair(_CP_INPUT, curses.COLOR_WHITE, curses.COLOR_BLUE)
            curses.init_pair(_CP_AUTHOR, curses.COLOR_CYAN, -1)

        self._started = True

    def stop(self) -> None:
        if not self._started:
            return
        self._started = False
        if self._scr is not None:
            try:
                self._scr.keypad(False)
            except curses.error:
                pass
        for fn in (
            lambda: curses.curs_set(1),
            curses.nocbreak,
            curses.echo,
            curses.endwin,
        ):
            try:
                fn()
            except curses.error:
                pass

    # ════════════════════════════════════════════════════════════════
    #  SAFE WRITE
    # ════════════════════════════════════════════════════════════════

    def _safe(self, row: int, col: int, text: str, attr: int = 0) -> None:
        """Write *text* at *(row, col)*, truncated to display width."""
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        if row < 0 or row >= rows or col < 0 or col >= cols:
            return
        avail = cols - col - 1
        if avail <= 0:
            return
        text = truncate_to_width(text, avail)
        try:
            self._scr.addstr(row, col, text, attr)
        except curses.error:
            cleaned = self._ascii_fallback(text)[:avail]
            try:
                self._scr.addstr(row, col, cleaned, attr)
            except curses.error:
                pass

    def _ascii_fallback(self, text: str) -> str:
        _MAP = {
            "📂": "[D]", "📄": "[F]", "📦": "[P]", "📋": "[=]",
            "📅": "[d]", "🔧": "[*]", "🔍": "[?]", "📝": "[>]",
            "🔖": "[B]", "🗂️": "[T]", "⚙️": "[S]", "📖": "[H]",
            "🔄": "[U]", "✅": "[v]", "👁️": "[E]", "🗑️": "[X]",
            "❌": "[x]", "➕": "[+]", "↩": "<-", "💾": "[s]",
            "🗑": "[X]", "📤": "[^]", "🚫": "[!]",
            "━": "=", "─": "-", "│": "|", "┌": "+", "┐": "+",
            "└": "+", "┘": "+", "├": "+", "┤": "+",
            "╔": "+", "╗": "+", "╚": "+", "╝": "+",
            "═": "=", "║": "|",
            "▸": ">", "▲": "^", "▼": "v",
            "✓": "x", "✗": "-",
            "❤️": "<3", "❤": "<3",
        }
        for k, v in _MAP.items():
            text = text.replace(k, v)
        return text.encode("ascii", errors="replace").decode("ascii")

    def _clear_row(self, row: int) -> None:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        if 0 <= row < rows:
            try:
                self._scr.move(row, 0)
                self._scr.clrtoeol()
            except curses.error:
                pass

    # ════════════════════════════════════════════════════════════════
    #  BOX HELPERS (display-width-aware)
    # ════════════════════════════════════════════════════════════════

    def _draw_box_line(
        self,
        row: int,
        left: str,
        fill: str,
        right: str,
        content: str,
        attr: int,
    ) -> None:
        """Render a single box row: ``left + padded_content + right``.

        *content* is padded/truncated to exactly ``self._inner_w`` display
        cells using :func:`display_width`.
        """
        iw = self._inner_w
        mg = self._margin

        if content == "":
            # Border-only line (top / bottom)
            line = left + fill * iw + right
        else:
            # Content line — pad with spaces to inner width
            content = truncate_to_width(content, iw)
            content = pad_right(content, iw)
            line = left + content + right

        self._safe(row, mg, line, attr)

    # ════════════════════════════════════════════════════════════════
    #  INPUT
    # ════════════════════════════════════════════════════════════════

    def get_key(self) -> KeyEvent:
        assert self._scr is not None
        try:
            ch = self._scr.get_wch()
        except curses.error:
            return KeyEvent(Key.UNKNOWN)
        except KeyboardInterrupt:
            return KeyEvent(Key.ESCAPE)

        if isinstance(ch, str):
            if len(ch) == 1:
                o = ord(ch)
                if o == 27:
                    return KeyEvent(Key.ESCAPE)
                if o in (10, 13):
                    return KeyEvent(Key.ENTER)
                if o == 32:
                    return KeyEvent(Key.SPACE)
                if o == 9:
                    return KeyEvent(Key.TAB)
                if o in (127, 8):
                    return KeyEvent(Key.BACKSPACE)
                if 32 <= o < 127 or o > 127:
                    return KeyEvent(Key.CHAR, ch)
            return KeyEvent(Key.CHAR, ch)
        return self._map_special(ch)

    def _map_special(self, ch: int) -> KeyEvent:
        _MAP: dict[int, Key] = {
            curses.KEY_UP: Key.UP,
            curses.KEY_DOWN: Key.DOWN,
            curses.KEY_LEFT: Key.LEFT,
            curses.KEY_RIGHT: Key.RIGHT,
            curses.KEY_ENTER: Key.ENTER,
            10: Key.ENTER, 13: Key.ENTER,
            curses.KEY_BACKSPACE: Key.BACKSPACE,
            127: Key.BACKSPACE, 8: Key.BACKSPACE,
            curses.KEY_HOME: Key.HOME,
            curses.KEY_END: Key.END,
            curses.KEY_PPAGE: Key.PAGE_UP,
            curses.KEY_NPAGE: Key.PAGE_DOWN,
            curses.KEY_DC: Key.DELETE,
            curses.KEY_RESIZE: Key.RESIZE,
            27: Key.ESCAPE,
        }
        key = _MAP.get(ch, Key.UNKNOWN)
        if key is Key.UNKNOWN and 32 <= ch < 127:
            return KeyEvent(Key.CHAR, chr(ch))
        return KeyEvent(key)

    def prompt(self, label: str, prefill: str = "") -> str | None:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        prompt_row = rows - 3
        curses.curs_set(1)
        buf: list[str] = list(prefill)

        while True:
            disp = "".join(buf)
            max_d = cols - len(label) - 3
            if len(disp) > max_d:
                disp = disp[-max_d:]
            self._clear_row(prompt_row)
            self._safe(prompt_row, 1, label, curses.color_pair(_CP_NAV))
            self._safe(prompt_row, len(label) + 1, disp)
            cx = min(len(label) + 1 + len(disp), cols - 1)
            try:
                self._scr.move(prompt_row, cx)
            except curses.error:
                pass
            self._scr.refresh()

            try:
                ch = self._scr.get_wch()
            except curses.error:
                continue
            except KeyboardInterrupt:
                curses.curs_set(0)
                return None

            if isinstance(ch, str):
                o = ord(ch) if len(ch) == 1 else 0
                if o == 27:
                    curses.curs_set(0)
                    return None
                if o in (10, 13):
                    curses.curs_set(0)
                    return "".join(buf)
                if o in (8, 127):
                    if buf:
                        buf.pop()
                else:
                    buf.append(ch)
            elif isinstance(ch, int):
                if ch == curses.KEY_BACKSPACE:
                    if buf:
                        buf.pop()
                elif ch in (curses.KEY_ENTER, 10, 13):
                    curses.curs_set(0)
                    return "".join(buf)
                elif ch == 27:
                    curses.curs_set(0)
                    return None

    def confirm(self, question: str) -> bool:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        r = rows - 3
        full = f"{question} (y/n): "
        self._clear_row(r)
        self._safe(r, 1, full, curses.color_pair(_CP_NAV))
        self._scr.refresh()
        while True:
            ev = self.get_key()
            if ev.key is Key.CHAR and ev.char.lower() in ("y", "n"):
                return ev.char.lower() == "y"
            if ev.key in (Key.ENTER, Key.ESCAPE):
                return False

    # ════════════════════════════════════════════════════════════════
    #  RENDERING
    # ════════════════════════════════════════════════════════════════

    def clear(self) -> None:
        assert self._scr is not None
        self._scr.erase()

    def get_size(self) -> tuple[int, int]:
        assert self._scr is not None
        return self._scr.getmaxyx()

    def draw_header(self, lines: list[str]) -> None:
        """Render boxed, centered header.

        lines[0] → title → ``╔═══╗`` cyan bold box
        lines[1] → stats → ``┌───┐`` dim/gray box
        lines[2:] → additional dim lines
        """
        assert self._scr is not None
        self._calc_layout()
        rows, _ = self.get_size()
        row = 0

        attr_t = curses.color_pair(_CP_TITLE) | curses.A_BOLD
        attr_s = curses.color_pair(_CP_DIM)

        # ── Title box ──
        if len(lines) >= 1 and lines[0].strip():
            txt = f" {lines[0].strip()} "
            self._draw_box_line(row, "╔", "═", "╗", "", attr_t)
            row += 1
            self._draw_box_line(row, "║", " ", "║", txt, attr_t)
            row += 1
            self._draw_box_line(row, "╚", "═", "╝", "", attr_t)
            row += 1

        # ── Stats box ──
        if len(lines) >= 2 and lines[1].strip():
            txt = f" {lines[1].strip()} "
            self._draw_box_line(row, "┌", "─", "┐", "", attr_s)
            row += 1
            self._draw_box_line(row, "│", " ", "│", txt, attr_s)
            row += 1
            self._draw_box_line(row, "└", "─", "┘", "", attr_s)
            row += 1

        # ── Extra lines ──
        for i in range(2, len(lines)):
            if row >= rows - 4:
                break
            if lines[i].strip():
                self._safe(row, self._margin, lines[i], attr_s)
                row += 1

        self._header_end = row
        self._scr.refresh()

    def draw_items(
        self,
        items: list[MenuItem],
        cursor: int,
        offset: int,
        visible_count: int,
    ) -> None:
        assert self._scr is not None
        self._calc_layout()
        rows, _ = self.get_size()
        start = self._header_end
        mg = self._margin
        pw = self._panel_w

        for vi in range(visible_count):
            idx = offset + vi
            row = start + vi
            if row >= rows - 3:
                break
            if idx >= len(items):
                break

            item = items[idx]
            is_cur = idx == cursor

            # ── Prefix ──
            if item.checked is not None:
                mark = "x" if item.checked else " "
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
                label = truncate_to_width(label, max(0, max_label - 1)) + "~"

            line = f"{prefix}{label}{suffix}"

            # ── Attribute ──
            if is_cur:
                attr = curses.color_pair(_CP_CURSOR) | curses.A_BOLD
            elif not item.enabled:
                attr = curses.color_pair(_CP_DIM) | curses.A_DIM
            elif item.checked:
                attr = curses.color_pair(_CP_CHECKED)
            else:
                attr = curses.color_pair(_CP_NORMAL)

            self._clear_row(row)
            self._safe(row, mg, line, attr)

        # ── Scroll indicators ──
        ind_col = mg + pw - 1
        if offset > 0:
            self._safe(start, ind_col, "▲", curses.color_pair(_CP_DIM))
        if offset + visible_count < len(items):
            last = start + min(visible_count, len(items) - offset) - 1
            if last < rows - 3:
                self._safe(last, ind_col, "▼", curses.color_pair(_CP_DIM))

        self._scr.refresh()

    def draw_footer(self, lines: list[str]) -> None:
        assert self._scr is not None
        self._calc_layout()
        rows, _ = self.get_size()
        total = len(lines)
        start_row = rows - total - 1
        mg = self._margin

        for i, line in enumerate(lines):
            row = start_row + i
            if row < 0 or row >= rows:
                continue
            self._clear_row(row)
            if i == total - 1:
                self._safe(row, mg, line, curses.color_pair(_CP_AUTHOR))
            else:
                self._safe(row, mg, line, curses.color_pair(_CP_NAV))
        self._scr.refresh()

    def draw_text_block(self, text: str) -> None:
        assert self._scr is not None
        text_lines = text.split("\n")
        offset = 0

        while True:
            rows, cols = self._scr.getmaxyx()
            self._scr.erase()
            visible = rows - 3

            for i in range(visible):
                li = offset + i
                if li >= len(text_lines):
                    break
                self._safe(i, 0, text_lines[li])

            tp = max(1, (len(text_lines) + visible - 1) // visible)
            cp = (offset // visible) + 1 if visible > 0 else 1
            hint = f" ↑↓:scroll  q/ESC:back  ({cp}/{tp})"
            self._safe(rows - 2, 0, hint, curses.color_pair(_CP_NAV))
            self._safe(rows - 1, 1, FOOTER_TEXT, curses.color_pair(_CP_AUTHOR))
            self._scr.refresh()

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
            elif ev.key is Key.RESIZE:
                continue

    def show_message(self, msg: str, wait: bool = True) -> None:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        lines = msg.split("\n")
        start_row = max(0, (rows - len(lines) - 2) // 2)
        self._scr.erase()
        attr = curses.color_pair(_CP_TITLE) | curses.A_BOLD
        for i, line in enumerate(lines):
            r = start_row + i
            if r >= rows - 2:
                break
            dw = display_width(line)
            x = max(0, (cols - dw) // 2)
            self._safe(r, x, line, attr)
        self._safe(rows - 1, 1, FOOTER_TEXT, curses.color_pair(_CP_AUTHOR))
        if wait:
            self._safe(rows - 2, 1, "Press any key...", curses.color_pair(_CP_DIM))
        self._scr.refresh()
        if wait:
            self.get_key()