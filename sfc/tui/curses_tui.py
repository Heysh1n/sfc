"""Curses-based TUI engine for POSIX systems (Linux / macOS)."""

from __future__ import annotations

import curses
import locale
import os

from .base import Engine, Key, KeyEvent, MenuItem


# ── Color pair IDs ──────────────────────────────────────────────────

_CP_NORMAL: int = 0
_CP_HEADER: int = 1
_CP_CURSOR: int = 2
_CP_CHECKED: int = 3
_CP_DIM: int = 4
_CP_FOOTER: int = 5
_CP_ERROR: int = 6
_CP_INPUT: int = 7


def _can_unicode() -> bool:
    """Check if the terminal likely supports unicode box-drawing + emoji."""
    enc = locale.getpreferredencoding(False).lower()
    lang = os.environ.get("LANG", "") + os.environ.get("LC_ALL", "")
    return "utf" in enc or "utf" in lang.lower()


class CursesEngine(Engine):
    """Concrete TUI engine backed by stdlib ``curses``."""

    def __init__(self) -> None:
        self._scr: curses.window | None = None
        self._started: bool = False
        self._unicode: bool = False

    # ════════════════════════════════════════════════════════════════
    #  LIFECYCLE
    # ════════════════════════════════════════════════════════════════

    def start(self) -> None:
        if self._started:
            return

        # Set locale BEFORE curses init — critical for wide-char support
        try:
            locale.setlocale(locale.LC_ALL, "")
        except locale.Error:
            pass

        self._unicode = _can_unicode()

        self._scr = curses.initscr()
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        self._scr.keypad(True)

        # Minimal delay for escape sequences
        os.environ.setdefault("ESCDELAY", "25")

        if curses.has_colors():
            curses.start_color()
            curses.use_default_colors()
            curses.init_pair(_CP_HEADER, curses.COLOR_CYAN, -1)
            curses.init_pair(_CP_CURSOR, curses.COLOR_BLACK, curses.COLOR_CYAN)
            curses.init_pair(_CP_CHECKED, curses.COLOR_GREEN, -1)
            curses.init_pair(_CP_DIM, curses.COLOR_WHITE, -1)
            curses.init_pair(_CP_FOOTER, curses.COLOR_YELLOW, -1)
            curses.init_pair(_CP_ERROR, curses.COLOR_RED, -1)
            curses.init_pair(_CP_INPUT, curses.COLOR_WHITE, curses.COLOR_BLUE)

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
        try:
            curses.curs_set(1)
        except curses.error:
            pass
        try:
            curses.nocbreak()
        except curses.error:
            pass
        try:
            curses.echo()
        except curses.error:
            pass
        try:
            curses.endwin()
        except curses.error:
            pass

    # ════════════════════════════════════════════════════════════════
    #  SAFE STRING HELPERS
    # ════════════════════════════════════════════════════════════════

    def _safe_addstr(
        self,
        row: int,
        col: int,
        text: str,
        attr: int = 0,
    ) -> None:
        """Write string, stripping problematic characters if needed."""
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        if row < 0 or row >= rows or col < 0 or col >= cols:
            return

        # Truncate to available width
        max_len = cols - col - 1
        if max_len <= 0:
            return
        text = text[:max_len]

        try:
            self._scr.addstr(row, col, text, attr)
        except curses.error:
            # Fallback: strip non-ASCII characters and retry
            cleaned = self._ascii_fallback(text)
            try:
                self._scr.addstr(row, col, cleaned[:max_len], attr)
            except curses.error:
                pass

    def _ascii_fallback(self, text: str) -> str:
        """Replace emoji and box-drawing chars with ASCII equivalents."""
        _MAP = {
            "📂": "[D]", "📄": "[F]", "📦": "[P]", "📋": "[=]",
            "📅": "[d]", "🔧": "[*]", "🔍": "[?]", "📝": "[>]",
            "🔖": "[B]", "🗂️": "[T]", "⚙️": "[S]", "📖": "[H]",
            "🔄": "[U]", "✅": "[v]", "👁️": "[E]", "🗑️": "[X]",
            "❌": "[x]", "➕": "[+]", "↩": "<-", "💾": "[s]",
            "🗑": "[X]", "📤": "[^]", "🚫": "[!]",
            "━": "=", "─": "-", "│": "|", "┌": "+", "┐": "+",
            "└": "+", "┘": "+", "├": "+", "┤": "+",
            "▸": ">", "▲": "^", "▼": "v",
            "✓": "x", "✗": "-",
        }
        for k, v in _MAP.items():
            text = text.replace(k, v)
        # Strip remaining non-ASCII if still problematic
        return text.encode("ascii", errors="replace").decode("ascii")

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
                o: int = ord(ch)
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
            10: Key.ENTER,
            13: Key.ENTER,
            curses.KEY_BACKSPACE: Key.BACKSPACE,
            127: Key.BACKSPACE,
            8: Key.BACKSPACE,
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
        prompt_row: int = rows - 2

        curses.curs_set(1)

        buf: list[str] = list(prefill)

        while True:
            display: str = "".join(buf)
            max_d: int = cols - len(label) - 3
            if len(display) > max_d:
                display = display[-max_d:]

            self._safe_addstr(prompt_row, 0, " " * (cols - 1))
            self._safe_addstr(prompt_row, 1, label, curses.color_pair(_CP_FOOTER))
            self._safe_addstr(prompt_row, len(label) + 1, display)

            cursor_x: int = min(len(label) + 1 + len(display), cols - 1)
            try:
                self._scr.move(prompt_row, cursor_x)
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
        prompt_row = rows - 2
        full = f"{question} (y/n): "
        self._safe_addstr(prompt_row, 0, " " * (cols - 1))
        self._safe_addstr(prompt_row, 1, full, curses.color_pair(_CP_FOOTER))
        self._scr.refresh()

        while True:
            ev = self.get_key()
            if ev.key is Key.CHAR and ev.char.lower() in ("y", "n"):
                return ev.char.lower() == "y"
            if ev.key is Key.ENTER:
                return False
            if ev.key is Key.ESCAPE:
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
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        attr = curses.color_pair(_CP_HEADER) | curses.A_BOLD
        for i, line in enumerate(lines):
            if i >= rows - 2:
                break
            self._safe_addstr(i, 0, line, attr)
        sep_row = len(lines)
        if sep_row < rows - 1:
            sep = "-" * min(cols - 1, 60)
            self._safe_addstr(sep_row, 0, sep, curses.color_pair(_CP_DIM))
        self._scr.refresh()

    def draw_items(
        self,
        items: list[MenuItem],
        cursor: int,
        offset: int,
        visible_count: int,
    ) -> None:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        # Start items right after the header separator
        start_row: int = self._get_item_start_row()

        for vi in range(visible_count):
            idx: int = offset + vi
            row: int = start_row + vi
            if row >= rows - 2:
                break
            if idx >= len(items):
                break

            item: MenuItem = items[idx]
            is_cur: bool = idx == cursor

            prefix: str
            if item.checked is not None:
                mark: str = "x" if item.checked else " "
                prefix = f" [{mark}] "
            else:
                prefix = "  "

            if is_cur:
                prefix = " >" + prefix[2:]

            label: str = item.label
            suffix: str = f"  {item.suffix}" if item.suffix else ""

            max_label: int = cols - len(prefix) - len(suffix) - 2
            if max_label > 0 and len(label) > max_label:
                label = label[:max_label - 1] + "~"

            line: str = f"{prefix}{label}{suffix}"

            if is_cur:
                attr = curses.color_pair(_CP_CURSOR) | curses.A_BOLD
            elif not item.enabled:
                attr = curses.color_pair(_CP_DIM) | curses.A_DIM
            elif item.checked:
                attr = curses.color_pair(_CP_CHECKED)
            else:
                attr = curses.color_pair(_CP_NORMAL)

            # Clear row first
            self._safe_addstr(row, 0, " " * (cols - 1), curses.color_pair(_CP_NORMAL))
            self._safe_addstr(row, 0, line, attr)

        # Scroll indicators (ASCII safe)
        if offset > 0:
            self._safe_addstr(start_row, cols - 2, "^", curses.color_pair(_CP_DIM))
        if offset + visible_count < len(items):
            last_vis = start_row + min(visible_count, len(items) - offset) - 1
            if last_vis < rows - 2:
                self._safe_addstr(last_vis, cols - 2, "v", curses.color_pair(_CP_DIM))

        self._scr.refresh()

    def draw_footer(self, lines: list[str]) -> None:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        for i, line in enumerate(lines):
            row = rows - len(lines) + i
            if row < 0:
                continue
            self._safe_addstr(row, 0, " " * (cols - 1))
            self._safe_addstr(row, 1, line, curses.color_pair(_CP_FOOTER))
        self._scr.refresh()

    def draw_text_block(self, text: str) -> None:
        assert self._scr is not None
        text_lines: list[str] = text.split("\n")
        offset: int = 0

        while True:
            rows, cols = self._scr.getmaxyx()
            self._scr.erase()
            visible = rows - 2

            for i in range(visible):
                li = offset + i
                if li >= len(text_lines):
                    break
                self._safe_addstr(i, 0, text_lines[li], curses.color_pair(_CP_NORMAL))

            total_pages = max(1, (len(text_lines) + visible - 1) // visible)
            cur_page = (offset // visible) + 1 if visible > 0 else 1
            hint = f" Up/Down:scroll  q/ESC:back  ({cur_page}/{total_pages})"
            self._safe_addstr(rows - 1, 0, hint, curses.color_pair(_CP_FOOTER))
            self._scr.refresh()

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
            elif ev.key is Key.RESIZE:
                continue

    def show_message(self, msg: str, wait: bool = True) -> None:
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        lines = msg.split("\n")
        start_row = max(0, (rows - len(lines)) // 2)
        self._scr.erase()
        attr = curses.color_pair(_CP_HEADER) | curses.A_BOLD
        for i, line in enumerate(lines):
            r = start_row + i
            if r >= rows:
                break
            x = max(0, (cols - len(line)) // 2)
            self._safe_addstr(r, x, line, attr)
        if wait:
            self._safe_addstr(rows - 1, 1, "Press any key...", curses.color_pair(_CP_DIM))
        self._scr.refresh()
        if wait:
            self.get_key()

    # ════════════════════════════════════════════════════════════════
    #  INTERNAL
    # ════════════════════════════════════════════════════════════════

    def _get_item_start_row(self) -> int:
        """Header lines + 1 separator.  Scan to find it reliably."""
        assert self._scr is not None
        rows, cols = self._scr.getmaxyx()
        for r in range(min(10, rows)):
            try:
                raw = self._scr.instr(r, 0, min(3, cols))
                # The separator is drawn as ASCII "-" now
                if raw.startswith(b"-") or raw.startswith(b"="):
                    return r + 1
            except curses.error:
                continue
        return 4