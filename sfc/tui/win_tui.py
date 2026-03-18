# fc/utils.py
"""Small helper functions used everywhere."""

import os


def term_width() -> int:
    try:
        return os.get_terminal_size().columns
    except OSError:
        return 80


def fmt_size(n: int) -> str:
    if n >= 1_048_576:
        return f"{n / 1_048_576:.1f}M"
    if n >= 1_024:
        return f"{n / 1_024:.1f}K"
    return f"{n}B"