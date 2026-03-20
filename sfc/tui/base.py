"""Abstract TUI engine protocol, key constants, MenuItem, and the
generic ``menu_loop`` that all screens share.

Every concrete engine (curses, win32) implements :class:`Engine` so the
application layer (``app.py``) never touches platform-specific code.

v4.0 changes:
  - ``FOOTER_TEXT`` rendered as a persistent bottom line on every screen.
  - Header split into *title box* (cyan) and *stats box* (dim/gray).
  - ``menu_loop`` accounts for the fixed 2-line footer.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Callable

from ..version import FOOTER_TEXT


# ════════════════════════════════════════════════════════════════════
#  KEY ENUMERATION
# ════════════════════════════════════════════════════════════════════

class Key(Enum):
    """Logical key identifiers returned by :meth:`Engine.get_key`."""
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
    """A single key press event.

    Attributes
    ----------
    key : Key
        The logical key.
    char : str
        For ``Key.CHAR`` events, the actual character.  Empty otherwise.
    """

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
    """A single selectable row in a TUI list / menu.

    Attributes
    ----------
    label : str
        Display text.
    value : str
        Machine-readable value (key, path, action id, …).
    checked : bool | None
        ``None`` → not checkable.  ``True`` / ``False`` → checkbox state.
    enabled : bool
        Greyed-out items can be shown but not selected.
    suffix : str
        Right-aligned secondary text (size, status, …).
    """

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
    """Abstract TUI rendering and input engine.

    Concrete implementations must support:
    - Full-screen clearing and repositioning
    - Rendering a list of items with a cursor and optional checkboxes
    - Blocking key input that returns :class:`KeyEvent`
    - A simple text input prompt (single line)
    - Status / message bar at the bottom
    - Fixed footer: ``Made with ❤️ by Heysh1n``
    """

    # ── Lifecycle ──

    @abstractmethod
    def start(self) -> None:
        """Enter TUI mode (hide cursor, alternate screen, raw mode, …)."""

    @abstractmethod
    def stop(self) -> None:
        """Leave TUI mode and restore terminal state."""

    # ── Input ──

    @abstractmethod
    def get_key(self) -> KeyEvent:
        """Block until a key is pressed and return the event."""

    @abstractmethod
    def prompt(self, label: str, prefill: str = "") -> str | None:
        """Show a one-line text input.  Return typed string or *None* on ESC."""

    @abstractmethod
    def confirm(self, question: str) -> bool:
        """Show a y/n prompt.  Return *True* for yes."""

    # ── Rendering ──

    @abstractmethod
    def clear(self) -> None:
        """Clear the entire screen."""

    @abstractmethod
    def get_size(self) -> tuple[int, int]:
        """Return ``(rows, cols)`` of the terminal."""

    @abstractmethod
    def draw_header(self, lines: list[str]) -> None:
        """Draw header lines at the top (title box + stats box)."""

    @abstractmethod
    def draw_items(
        self,
        items: list[MenuItem],
        cursor: int,
        offset: int,
        visible_count: int,
    ) -> None:
        """Draw a scrollable item list."""

    @abstractmethod
    def draw_footer(self, lines: list[str]) -> None:
        """Draw navigation hints + fixed ``Made with ❤️`` line at bottom."""

    @abstractmethod
    def draw_text_block(self, text: str) -> None:
        """Render a scrollable multi-line text block (help, previews, etc.)."""

    @abstractmethod
    def show_message(self, msg: str, wait: bool = True) -> None:
        """Show a temporary message.  If *wait*, block until key press."""

    # ── High-level: generic menu loop ──

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

            # Header uses boxes: 3 rows per box (title + stats = 6)
            # Extra lines beyond [0] and [1] add 1 row each
            header_rows: int = 0
            if len(title) >= 1 and title[0].strip():
                header_rows += 3  # title box
            if len(title) >= 2 and title[1].strip():
                header_rows += 3  # stats box
            for i in range(2, len(title)):
                if title[i].strip():
                    header_rows += 1

            footer_rows: int = len(footer_lines) + 2
            visible: int = max(1, rows - header_rows - footer_rows)

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
                        return items[cursor] if 0 <= cursor < len(items) else None
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
        """Move cursor by *delta*, skipping disabled items."""
        n: int = len(items)
        if n == 0:
            return 0
        target: int = max(0, min(current + delta, n - 1))
        step: int = 1 if delta >= 0 else -1
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