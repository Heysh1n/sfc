"""Abstract TUI engine, key constants, MenuItem, width utilities,
and the generic ``menu_loop``.

v4.0.1 fixes:
  - ``display_width()`` using ``unicodedata`` for correct emoji cell widths
  - ``pad_right()`` / ``truncate_to_width()`` based on visual cells
  - ``header_height()`` for accurate layout math
  - All rendering uses display-width-aware padding
"""

from __future__ import annotations

import unicodedata
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Callable

from ..version import FOOTER_TEXT


# ════════════════════════════════════════════════════════════════════
#  DISPLAY WIDTH UTILITIES
# ════════════════════════════════════════════════════════════════════

# BMP codepoints that most terminals render as width 2
# despite having East Asian Width = Neutral
_WIDE_EMOJI: frozenset[int] = frozenset({
    0x231A, 0x231B, 0x23E9, 0x23EA, 0x23EB, 0x23EC, 0x23F0, 0x23F3,
    0x23F8, 0x23F9, 0x23FA, 0x25FD, 0x25FE, 0x2614, 0x2615, 0x2648,
    0x2649, 0x264A, 0x264B, 0x264C, 0x264D, 0x264E, 0x264F, 0x2650,
    0x2651, 0x2652, 0x2653, 0x267F, 0x2693, 0x2694, 0x2696, 0x2697,
    0x2699, 0x269B, 0x269C, 0x26A1, 0x26AA, 0x26AB, 0x26BD, 0x26BE,
    0x26C4, 0x26C5, 0x26CE, 0x26D4, 0x26EA, 0x26F2, 0x26F3, 0x26F5,
    0x26FA, 0x26FD, 0x2702, 0x2705, 0x2708, 0x2709, 0x270A, 0x270B,
    0x270C, 0x270D, 0x270F, 0x2712, 0x2714, 0x2716, 0x271D, 0x2721,
    0x2728, 0x2733, 0x2734, 0x2744, 0x2747, 0x274C, 0x274E, 0x2753,
    0x2754, 0x2755, 0x2757, 0x2763, 0x2764, 0x2795, 0x2796, 0x2797,
    0x27A1, 0x27B0, 0x27BF, 0x2934, 0x2935, 0x2B05, 0x2B06, 0x2B07,
    0x2B1B, 0x2B1C, 0x2B50, 0x2B55, 0x3030, 0x303D, 0x3297, 0x3299,
})

PANEL_MAX_INNER: int = 56


def _char_width(ch: str) -> int:
    """Display cell width of a single character in a monospace terminal."""
    cp = ord(ch)

    # Zero-width: combining marks, format chars, variation selectors
    cat = unicodedata.category(ch)
    if cat.startswith("M"):      # Mn, Mc, Me
        return 0
    if cat == "Cf":              # Includes ZWJ U+200D, soft-hyphen, etc.
        return 0
    if 0xFE00 <= cp <= 0xFE0F:   # Variation selectors VS1–VS16
        return 0
    if 0xE0100 <= cp <= 0xE01EF: # Supplementary variation selectors
        return 0
    if cp in (0x200B, 0xFEFF):   # Zero-width space, BOM
        return 0

    # East Asian Wide / Fullwidth
    eaw = unicodedata.east_asian_width(ch)
    if eaw in ("W", "F"):
        return 2

    # Supplementary planes: emoji, pictographs, symbols → width 2
    if cp >= 0x10000:
        return 2

    # Known wide BMP emoji
    if cp in _WIDE_EMOJI:
        return 2

    return 1


def display_width(text: str) -> int:
    """Terminal cell width of *text*, accounting for wide chars and emoji."""
    return sum(_char_width(ch) for ch in text)


def pad_right(text: str, target_width: int) -> str:
    """Pad *text* with spaces so its display width equals *target_width*.

    If the text is already wider than *target_width*, it is returned as-is.
    """
    current = display_width(text)
    if current >= target_width:
        return text
    return text + " " * (target_width - current)


def truncate_to_width(text: str, max_width: int) -> str:
    """Truncate *text* so its display width does not exceed *max_width*."""
    if max_width <= 0:
        return ""
    w = 0
    end = 0
    for i, ch in enumerate(text):
        cw = _char_width(ch)
        if w + cw > max_width:
            break
        w += cw
        end = i + 1
    return text[:end]


# ════════════════════════════════════════════════════════════════════
#  KEY ENUMERATION
# ════════════════════════════════════════════════════════════════════

class Key(Enum):
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    ENTER = auto()
    SPACE = auto()
    ESCAPE = auto()
    BACKSPACE = auto()
    TAB = auto()
    HOME = auto()
    END = auto()
    PAGE_UP = auto()
    PAGE_DOWN = auto()
    DELETE = auto()
    CHAR = auto()
    RESIZE = auto()
    UNKNOWN = auto()


class KeyEvent:
    __slots__ = ("key", "char")

    def __init__(self, key: Key, char: str = "") -> None:
        self.key = key
        self.char = char

    def __repr__(self) -> str:
        if self.key is Key.CHAR:
            return f"KeyEvent(CHAR, {self.char!r})"
        return f"KeyEvent({self.key.name})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, KeyEvent):
            return self.key == other.key and self.char == other.char
        if isinstance(other, Key):
            return self.key == other
        return NotImplemented

    def __hash__(self) -> int:
        return hash((self.key, self.char))

    @property
    def is_printable(self) -> bool:
        return self.key is Key.CHAR and len(self.char) == 1


# ════════════════════════════════════════════════════════════════════
#  MENU ITEM
# ════════════════════════════════════════════════════════════════════

class MenuItem:
    __slots__ = ("label", "value", "checked", "enabled", "suffix")

    def __init__(
        self,
        label: str,
        value: str = "",
        *,
        checked: bool | None = None,
        enabled: bool = True,
        suffix: str = "",
    ) -> None:
        self.label = label
        self.value = value or label
        self.checked = checked
        self.enabled = enabled
        self.suffix = suffix

    def __repr__(self) -> str:
        chk = ""
        if self.checked is not None:
            chk = f" [{'x' if self.checked else ' '}]"
        return f"MenuItem({self.label!r}{chk})"


# ════════════════════════════════════════════════════════════════════
#  ABSTRACT ENGINE
# ════════════════════════════════════════════════════════════════════

class Engine(ABC):

    # ── Lifecycle ──

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    # ── Input ──

    @abstractmethod
    def get_key(self) -> KeyEvent: ...

    @abstractmethod
    def prompt(self, label: str, prefill: str = "") -> str | None: ...

    @abstractmethod
    def confirm(self, question: str) -> bool: ...

    # ── Rendering ──

    @abstractmethod
    def clear(self) -> None: ...

    @abstractmethod
    def get_size(self) -> tuple[int, int]: ...

    @abstractmethod
    def draw_header(self, lines: list[str]) -> None: ...

    @abstractmethod
    def draw_items(
        self,
        items: list[MenuItem],
        cursor: int,
        offset: int,
        visible_count: int,
    ) -> None: ...

    @abstractmethod
    def draw_footer(self, lines: list[str]) -> None: ...

    @abstractmethod
    def draw_text_block(self, text: str) -> None: ...

    @abstractmethod
    def show_message(self, msg: str, wait: bool = True) -> None: ...

    # ── Layout helpers ──

    def header_height(self, lines: list[str]) -> int:
        """Calculate how many terminal rows the header boxes will occupy."""
        h = 0
        if len(lines) >= 1 and lines[0].strip():
            h += 3  # title box (top + content + bottom)
        if len(lines) >= 2 and lines[1].strip():
            h += 3  # stats box
        for i in range(2, len(lines)):
            if lines[i].strip():
                h += 1
        return h

    # ── Generic menu loop ──

    def menu_loop(
        self,
        title: list[str],
        items: list[MenuItem],
        footer: list[str] | None = None,
        on_select: Callable[[MenuItem, int], bool | None] | None = None,
        on_check: Callable[[MenuItem, int], None] | None = None,
        on_key: Callable[[KeyEvent, list[MenuItem], int], int | None] | None = None,
    ) -> MenuItem | None:
        if not items:
            return None

        cursor: int = 0
        offset: int = 0

        for i, item in enumerate(items):
            if item.enabled:
                cursor = i
                break

        footer_lines: list[str] = list(footer) if footer else []

        while True:
            rows, cols = self.get_size()

            header_rows = self.header_height(title)
            footer_rows = len(footer_lines) + 2  # nav hints + author
            visible = max(1, rows - header_rows - footer_rows)

            if cursor < offset:
                offset = cursor
            elif cursor >= offset + visible:
                offset = cursor - visible + 1

            self.clear()
            self.draw_header(title)
            self.draw_items(items, cursor, offset, visible)

            full_footer = list(footer_lines) + [FOOTER_TEXT]
            self.draw_footer(full_footer)

            ev: KeyEvent = self.get_key()

            if on_key is not None:
                new_cur = on_key(ev, items, cursor)
                if new_cur is not None:
                    if new_cur == -999:
                        return (
                            items[cursor]
                            if 0 <= cursor < len(items)
                            else None
                        )
                    cursor = max(0, min(new_cur, len(items) - 1))
                    continue

            if ev.key is Key.ESCAPE:
                return None
            if ev.key is Key.RESIZE:
                continue

            if ev.key is Key.UP:
                cursor = self._move_cursor(items, cursor, -1)
            elif ev.key is Key.DOWN:
                cursor = self._move_cursor(items, cursor, +1)
            elif ev.key is Key.HOME:
                cursor = self._first_enabled(items)
            elif ev.key is Key.END:
                cursor = self._last_enabled(items)
            elif ev.key is Key.PAGE_UP:
                cursor = self._move_cursor(items, cursor, -visible)
            elif ev.key is Key.PAGE_DOWN:
                cursor = self._move_cursor(items, cursor, +visible)
            elif ev.key is Key.SPACE:
                item = items[cursor]
                if item.enabled and item.checked is not None:
                    item.checked = not item.checked
                    if on_check is not None:
                        on_check(item, cursor)
                    cursor = self._move_cursor(items, cursor, +1)
            elif ev.key is Key.ENTER:
                item = items[cursor]
                if item.enabled:
                    if on_select is not None:
                        if on_select(item, cursor):
                            return item
                    else:
                        return item

    # ── Cursor helpers ──

    @staticmethod
    def _move_cursor(items: list[MenuItem], current: int, delta: int) -> int:
        n = len(items)
        if n == 0:
            return 0
        target = max(0, min(current + delta, n - 1))
        step = 1 if delta >= 0 else -1
        while 0 <= target < n and not items[target].enabled:
            target += step
        if target < 0 or target >= n:
            target = current
        return target

    @staticmethod
    def _first_enabled(items: list[MenuItem]) -> int:
        for i, item in enumerate(items):
            if item.enabled:
                return i
        return 0

    @staticmethod
    def _last_enabled(items: list[MenuItem]) -> int:
        for i in range(len(items) - 1, -1, -1):
            if items[i].enabled:
                return i
        return len(items) - 1