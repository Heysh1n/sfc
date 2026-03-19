"""Self-updater: check remote version, download, overwrite, prompt restart.

v4.0 additions:
  - Binary update support for compiled ``.exe`` (Windows) and ELF (Linux/macOS)
  - Detached batch-script workaround on Windows to replace a running ``.exe``
  - GitHub Releases API for fetching binary assets

Works with:
  - ``.py`` / package dir  → overwrite individual module files
  - ``.pyz`` zipapp        → overwrite the archive
  - ``.exe`` (Windows)     → detached ``.bat`` script swaps the binary
  - ELF / Mach-O binary    → atomic rename (not locked on POSIX)

No third-party dependencies — uses only ``urllib`` and ``json``.
"""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, NamedTuple
from urllib.error import URLError
from urllib.request import Request, urlopen

from .version import GITHUB_RAW_BASE, GITHUB_RELEASES_API, VERSION


# ════════════════════════════════════════════════════════════════════
#  PUBLIC TYPES
# ════════════════════════════════════════════════════════════════════

class UpdateCheckResult(NamedTuple):
    """Outcome of a version check."""
    available: bool         # True if a newer version exists
    remote_version: str     # version string from remote, or "" on error
    current_version: str    # local VERSION
    error: str              # human-readable error, or ""


class UpdateApplyResult(NamedTuple):
    """Outcome of an apply attempt."""
    ok: bool
    message: str


# ════════════════════════════════════════════════════════════════════
#  INTERNALS — VERSION PARSING
# ════════════════════════════════════════════════════════════════════

_TIMEOUT: int = 10
_VERSION_URL: str = f"{GITHUB_RAW_BASE}/sfc/version.py"

# Module files for package-mode update
_PACKAGE_FILES: list[str] = [
    "__init__.py",
    "__main__.py",
    "version.py",
    "patterns.py",
    "config.py",
    "collector.py",
    "clipboard.py",
    "updater.py",
    "app.py",
    "tui/__init__.py",
    "tui/base.py",
    "tui/curses_tui.py",
    "tui/win_tui.py",
]


def _fetch(url: str) -> bytes:
    """Fetch URL contents.  Raises on failure."""
    req = Request(url, headers={"User-Agent": "sfc-updater/4.0"})
    with urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read()


def _parse_remote_version(raw: bytes) -> str:
    """Extract ``VERSION = "x.y.z"`` from raw ``version.py`` bytes."""
    text: str = raw.decode("utf-8", errors="replace")
    match = re.search(r'VERSION\s*[=:]\s*["\']([^"\']+)["\']', text)
    return match.group(1) if match else ""


def _version_tuple(v: str) -> tuple[int, ...]:
    """``"4.0.0"`` → ``(4, 0, 0)``.  Non-numeric parts become 0."""
    parts: list[int] = []
    for segment in v.split("."):
        try:
            parts.append(int(segment))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_newer(remote: str, local: str) -> bool:
    """Return True if *remote* is strictly greater than *local*."""
    return _version_tuple(remote) > _version_tuple(local)


# ════════════════════════════════════════════════════════════════════
#  EXECUTABLE DETECTION
# ════════════════════════════════════════════════════════════════════

class _ExeKind:
    """Classification of the running executable."""
    PACKAGE = "package"     # python -m sfc (directory with version.py)
    ZIPAPP = "zipapp"       # sfc.pyz
    BINARY_WIN = "exe"      # sfc.exe (frozen PyInstaller on Windows)
    BINARY_POSIX = "elf"    # sfc (frozen PyInstaller on Linux/macOS)
    UNKNOWN = "unknown"


def _executable_path() -> Path:
    """Best guess at the currently running script / archive / binary."""
    # PyInstaller sets sys._MEIPASS and rewrites sys.executable
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()

    candidate = Path(sys.argv[0]).resolve()
    if candidate.exists():
        return candidate

    main_mod = sys.modules.get("__main__")
    if main_mod and hasattr(main_mod, "__file__") and main_mod.__file__:
        candidate = Path(main_mod.__file__).resolve()
        if candidate.exists():
            return candidate

    return Path(__file__).resolve()


def _detect_kind(exe: Path) -> str:
    """Determine what kind of executable we are running as."""
    if getattr(sys, "frozen", False):
        if sys.platform == "win32":
            return _ExeKind.BINARY_WIN
        return _ExeKind.BINARY_POSIX

    if exe.suffix.lower() == ".pyz":
        return _ExeKind.ZIPAPP

    # Check if we're inside a package directory
    if exe.parent.name == "sfc" and (exe.parent / "version.py").exists():
        return _ExeKind.PACKAGE

    return _ExeKind.UNKNOWN


def _is_writable(p: Path) -> bool:
    """Check if we can write to *p* (or its parent if *p* doesn't exist)."""
    if p.exists():
        return os.access(p, os.W_OK)
    return os.access(p.parent, os.W_OK)


# ════════════════════════════════════════════════════════════════════
#  GITHUB RELEASES API — BINARY ASSET DOWNLOAD
# ════════════════════════════════════════════════════════════════════

def _get_release_asset_url(asset_name_hint: str) -> str | None:
    """Query the GitHub Releases API for the latest release and return
    the download URL of the asset whose name contains *asset_name_hint*.

    Returns *None* if no matching asset is found or on network error.
    """
    try:
        raw: bytes = _fetch(GITHUB_RELEASES_API)
        data: dict[str, Any] = json.loads(raw)
    except (URLError, OSError, json.JSONDecodeError):
        return None

    assets: list[dict[str, Any]] = data.get("assets", [])
    hint_lower = asset_name_hint.lower()

    for asset in assets:
        name: str = asset.get("name", "")
        if hint_lower in name.lower():
            return asset.get("browser_download_url", "")

    return None


# ════════════════════════════════════════════════════════════════════
#  ATOMIC WRITE
# ════════════════════════════════════════════════════════════════════

def _atomic_write(target: Path, data: bytes) -> None:
    """Write *data* to a temp file then rename over *target*.

    On Windows ``os.replace`` can fail if the file is locked; in that case
    we fall back to direct write.
    """
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, tmp_path_str = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.stem}_",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_path_str)
    try:
        os.write(fd, data)
        os.close(fd)
        fd = -1

        try:
            os.replace(str(tmp_path), str(target))
        except OSError:
            target.write_bytes(data)
            try:
                tmp_path.unlink()
            except OSError:
                pass
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


# ════════════════════════════════════════════════════════════════════
#  WINDOWS .EXE — DETACHED BATCH SCRIPT WORKAROUND
# ════════════════════════════════════════════════════════════════════

_BATCH_TEMPLATE: str = """\
@echo off
:: sfc self-updater — replaces the running .exe
:: Waits for the original process to exit, then swaps files.

set "TARGET={target}"
set "NEW_FILE={new_file}"
set "PID={pid}"

echo [sfc-update] Waiting for process %PID% to exit...

:wait_loop
tasklist /FI "PID eq %PID%" 2>NUL | find /I "%PID%" >NUL
if not errorlevel 1 (
    timeout /t 1 /nobreak >NUL
    goto wait_loop
)

echo [sfc-update] Process exited.  Replacing executable...

:: Retry loop — file may still be locked briefly after process exit
set RETRIES=0

:replace_loop
if %RETRIES% GEQ 10 (
    echo [sfc-update] ERROR: Could not replace %TARGET% after 10 retries.
    pause
    goto cleanup
)

del /f "%TARGET%" 2>NUL
if exist "%TARGET%" (
    set /a RETRIES+=1
    timeout /t 1 /nobreak >NUL
    goto replace_loop
)

move /y "%NEW_FILE%" "%TARGET%"
if errorlevel 1 (
    echo [sfc-update] ERROR: Move failed.
    pause
    goto cleanup
)

echo [sfc-update] Update complete.  You can restart sfc now.

:cleanup
:: Self-delete this batch file
del /f "%~f0" 2>NUL
"""


def _launch_bat_replacer(exe_path: Path, new_data: bytes) -> UpdateApplyResult:
    """Write *new_data* to a temp file next to *exe_path*, then launch a
    detached ``.bat`` script that waits for the current process to die,
    deletes the old ``.exe``, and moves the new one into place.

    This is the canonical workaround for replacing a running ``.exe`` on
    Windows — the OS locks the file while it's executing.
    """
    new_file = exe_path.parent / f".sfc_update_{os.getpid()}.exe"
    bat_file = exe_path.parent / f".sfc_update_{os.getpid()}.bat"

    try:
        new_file.write_bytes(new_data)
    except OSError as exc:
        return UpdateApplyResult(ok=False, message=f"write failed: {exc}")

    bat_content = _BATCH_TEMPLATE.format(
        target=str(exe_path),
        new_file=str(new_file),
        pid=os.getpid(),
    )

    try:
        bat_file.write_text(bat_content, encoding="utf-8")
    except OSError as exc:
        new_file.unlink(missing_ok=True)
        return UpdateApplyResult(ok=False, message=f"bat write failed: {exc}")

    # Launch detached — CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    DETACHED_PROCESS = 0x00000008

    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(bat_file)],
            creationflags=CREATE_NEW_PROCESS_GROUP | DETACHED_PROCESS,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            stdin=subprocess.DEVNULL,
            close_fds=True,
        )
    except OSError as exc:
        new_file.unlink(missing_ok=True)
        bat_file.unlink(missing_ok=True)
        return UpdateApplyResult(ok=False, message=f"failed to launch updater: {exc}")

    return UpdateApplyResult(
        ok=True,
        message=(
            "Update downloaded.  sfc will close now.\n"
            "The updater script will replace the .exe automatically.\n"
            "Please restart sfc after a few seconds."
        ),
    )


# ════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════

def check_update() -> UpdateCheckResult:
    """Check GitHub for a newer version.  Network errors are caught."""
    try:
        raw: bytes = _fetch(_VERSION_URL)
    except (URLError, OSError, TimeoutError) as exc:
        return UpdateCheckResult(
            available=False,
            remote_version="",
            current_version=VERSION,
            error=f"network error: {exc}",
        )

    remote: str = _parse_remote_version(raw)
    if not remote:
        return UpdateCheckResult(
            available=False,
            remote_version="",
            current_version=VERSION,
            error="could not parse remote version",
        )

    return UpdateCheckResult(
        available=_is_newer(remote, VERSION),
        remote_version=remote,
        current_version=VERSION,
        error="",
    )


def apply_update() -> UpdateApplyResult:
    """Download the latest version and overwrite the current executable.

    Strategy per exe kind:

    ``package``
        Overwrite each module file individually from ``GITHUB_RAW_BASE``.

    ``zipapp`` (``.pyz``)
        Try to download ``sfc.pyz`` from GitHub Releases.
        Fallback: overwrite as package if the ``.pyz`` asset is absent.

    ``exe`` (Windows ``.exe``)
        Download ``sfc.exe`` from GitHub Releases, write to temp file,
        launch a detached ``.bat`` that waits for this process to die
        then swaps the files.

    ``elf`` (Linux / macOS binary)
        Download ``sfc`` from GitHub Releases, atomic-rename over the
        current binary (POSIX doesn't lock running executables).
    """
    exe: Path = _executable_path()
    kind: str = _detect_kind(exe)

    if not _is_writable(exe):
        return UpdateApplyResult(
            ok=False,
            message=f"no write permission: {exe}",
        )

    try:
        # ── Package mode ────────────────────────────────────────
        if kind == _ExeKind.PACKAGE:
            return _update_package(exe)

        # ── Zipapp mode ─────────────────────────────────────────
        if kind == _ExeKind.ZIPAPP:
            return _update_zipapp(exe)

        # ── Windows .exe ─────────────────────────────────────────
        if kind == _ExeKind.BINARY_WIN:
            return _update_binary_win(exe)

        # ── Linux/macOS binary ───────────────────────────────────
        if kind == _ExeKind.BINARY_POSIX:
            return _update_binary_posix(exe)

        # ── Unknown — try package-style as best effort ───────────
        return _update_package(exe)

    except Exception as exc:
        return UpdateApplyResult(ok=False, message=f"update failed: {exc}")


# ════════════════════════════════════════════════════════════════════
#  PER-KIND UPDATE IMPLEMENTATIONS
# ════════════════════════════════════════════════════════════════════

def _update_package(exe: Path) -> UpdateApplyResult:
    """Overwrite individual module files from GitHub raw."""
    package_dir: Path
    if exe.parent.name == "sfc" and (exe.parent / "version.py").exists():
        package_dir = exe.parent
    elif exe.name == "__main__.py":
        package_dir = exe.parent
    else:
        package_dir = exe.parent / "sfc"

    if not package_dir.is_dir():
        return UpdateApplyResult(
            ok=False,
            message=f"package dir not found: {package_dir}",
        )

    updated: int = 0
    errors: list[str] = []

    for rel in _PACKAGE_FILES:
        url: str = f"{GITHUB_RAW_BASE}/sfc/{rel}"
        target: Path = package_dir / rel
        try:
            data: bytes = _fetch(url)
        except (URLError, OSError) as exc:
            errors.append(f"{rel}: {exc}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(target, data)
        updated += 1

    if updated == 0:
        return UpdateApplyResult(
            ok=False,
            message=f"no files updated — errors: {'; '.join(errors)}",
        )

    msg = f"updated {updated}/{len(_PACKAGE_FILES)} files — please restart sfc"
    if errors:
        msg += f"\n⚠️ skipped: {', '.join(e.split(':')[0] for e in errors)}"
    return UpdateApplyResult(ok=True, message=msg)


def _update_zipapp(exe: Path) -> UpdateApplyResult:
    """Download ``sfc.pyz`` from GitHub Releases and replace."""
    url = _get_release_asset_url("sfc.pyz")
    if url:
        try:
            data = _fetch(url)
            _atomic_write(exe, data)
            if os.name != "nt":
                exe.chmod(
                    exe.stat().st_mode
                    | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH,
                )
            return UpdateApplyResult(
                ok=True,
                message=f"updated {exe.name} — please restart sfc",
            )
        except (URLError, OSError) as exc:
            pass  # fall through to package-style

    # Fallback: update as package (if the pyz was extracted somewhere)
    return _update_package(exe)


def _update_binary_win(exe: Path) -> UpdateApplyResult:
    """Download ``sfc.exe`` from GitHub Releases and use the batch-script
    workaround to replace the running executable."""
    url = _get_release_asset_url("sfc.exe")
    if not url:
        return UpdateApplyResult(
            ok=False,
            message="sfc.exe not found in latest GitHub release assets",
        )

    try:
        data = _fetch(url)
    except (URLError, OSError) as exc:
        return UpdateApplyResult(ok=False, message=f"download failed: {exc}")

    if len(data) < 1024:
        return UpdateApplyResult(
            ok=False,
            message="downloaded file too small — likely not a valid binary",
        )

    return _launch_bat_replacer(exe, data)


def _update_binary_posix(exe: Path) -> UpdateApplyResult:
    """Download the binary from GitHub Releases and atomic-rename.

    On POSIX, a running binary is *not* locked — ``os.replace`` works
    even while the process is executing (the old inode stays alive until
    the process exits).
    """
    # Try platform-specific asset name
    if sys.platform == "darwin":
        hint = "sfc-macos"
    else:
        hint = "sfc-linux"

    url = _get_release_asset_url(hint)

    # Fallback: generic "sfc" asset
    if not url:
        url = _get_release_asset_url("sfc")

    if not url:
        return UpdateApplyResult(
            ok=False,
            message=f"binary asset not found in latest GitHub release",
        )

    try:
        data = _fetch(url)
    except (URLError, OSError) as exc:
        return UpdateApplyResult(ok=False, message=f"download failed: {exc}")

    if len(data) < 1024:
        return UpdateApplyResult(
            ok=False,
            message="downloaded file too small — likely not a valid binary",
        )

    _atomic_write(exe, data)

    # Restore executable permissions
    try:
        exe.chmod(
            exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH,
        )
    except OSError:
        pass

    return UpdateApplyResult(
        ok=True,
        message=f"updated {exe.name} — please restart sfc",
    )