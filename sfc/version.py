"""Single source of truth for version and application metadata."""

from __future__ import annotations

__version__ = "4.9.1"
VERSION: str = __version__
APP_NAME: str = "SFC"
APP_TITLE: str = "Smart File Collector"
AUTHOR: str = "Heysh1n"
AUTHOR_URL: str = "https://github.com/Heysh1n"
FOOTER_TEXT: str = (
    f"Made with \u2764\ufe0f by "
    f"\033]8;;{AUTHOR_URL}\033\\{AUTHOR}\033]8;;\033\\"
)

GITHUB_REPO: str = "Heysh1n/sfc"
GITHUB_RAW_BASE: str = (
    f"https://raw.githubusercontent.com/{GITHUB_REPO}/master"
)
GITHUB_RELEASES_API: str = (
    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
)