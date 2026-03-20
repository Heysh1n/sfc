"""Self-updater: check remote version, download, overwrite, prompt restart.

v4.0.1 — bulletproof pipeline:
  1. Fetch version.py from raw GitHub → parse remote VERSION
  2. Download new executable to a temp file
  3. Windows .exe: detached .bat waits 2s, replaces, relaunches, self-deletes
  4. Linux/macOS: os.replace() (POSIX never locks running binaries)
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
    available: bool
    remote_version: str
    current_version: str
    error: str


class UpdateApplyResult(NamedTuple):
    ok: bool
    message: str


# ════════════════════════════════════════════════════════════════════
#  INTERNALS
# ════════════════════════════════════════════════════════════════════

_TIMEOUT: int = 10
_VERSION_URL: str = f"{GITHUB_RAW_BASE}/sfc/version.py"

_PACKAGE_FILES: list[str] = [
    "__init__.py", "__main__.py", "version.py", "patterns.py",
    "config.py", "collector.py", "clipboard.py", "updater.py", "app.py",
    "tui/__init__.py", "tui/base.py", "tui/curses_tui.py", "tui/win_tui.py",
]


def _fetch(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "sfc-updater/4.0"})
    with urlopen(req, timeout=_TIMEOUT) as resp:
        return resp.read()


def _parse_remote_version(raw: bytes) -> str:
    text = raw.decode("utf-8", errors="replace")
    m = re.search(r'VERSION\s*[=:]\s*["\']([^"\']+)["\']', text)
    return m.group(1) if m else ""


def _vtuple(v: str) -> tuple[int, ...]:
    parts: list[int] = []
    for s in v.split("."):
        try:
            parts.append(int(s))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def _is_newer(remote: str, local: str) -> bool:
    return _vtuple(remote) > _vtuple(local)


# ── Executable detection ────────────────────────────────────────────

class _Kind:
    PACKAGE = "package"
    ZIPAPP = "zipapp"
    EXE = "exe"
    ELF = "elf"
    UNKNOWN = "unknown"


def _exe_path() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve()
    c = Path(sys.argv[0]).resolve()
    if c.exists():
        return c
    m = sys.modules.get("__main__")
    if m and getattr(m, "__file__", None):
        c = Path(m.__file__).resolve()
        if c.exists():
            return c
    return Path(__file__).resolve()


def _detect_kind(exe: Path) -> str:
    if getattr(sys, "frozen", False):
        return _Kind.EXE if sys.platform == "win32" else _Kind.ELF
    if exe.suffix.lower() == ".pyz":
        return _Kind.ZIPAPP
    if exe.parent.name == "sfc" and (exe.parent / "version.py").exists():
        return _Kind.PACKAGE
    return _Kind.UNKNOWN


def _is_writable(p: Path) -> bool:
    return os.access(p, os.W_OK) if p.exists() else os.access(p.parent, os.W_OK)


# ── GitHub Releases API ─────────────────────────────────────────────

def _get_asset_url(hint: str) -> str | None:
    try:
        raw = _fetch(GITHUB_RELEASES_API)
        data: dict[str, Any] = json.loads(raw)
    except (URLError, OSError, json.JSONDecodeError):
        return None
    hl = hint.lower()
    for asset in data.get("assets", []):
        if hl in asset.get("name", "").lower():
            return asset.get("browser_download_url", "")
    return None


# ── Atomic write ─────────────────────────────────────────────────────

def _atomic_write(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.stem}_", suffix=".tmp",
    )
    tmp_path = Path(tmp)
    try:
        os.write(fd, data)
        os.close(fd)
        fd = -1
        try:
            os.replace(str(tmp_path), str(target))
        except OSError:
            target.write_bytes(data)
            tmp_path.unlink(missing_ok=True)
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        tmp_path.unlink(missing_ok=True)


# ════════════════════════════════════════════════════════════════════
#  WINDOWS .EXE — DETACHED BATCH SCRIPT
# ════════════════════════════════════════════════════════════════════

_BAT = """\
@echo off
:: sfc self-updater — replaces running .exe after it exits
set "TARGET={target}"
set "NEW={new_file}"

echo [sfc-update] Waiting 2 seconds for process to release file...
timeout /t 2 /nobreak >NUL

:: Retry delete up to 10 times (file may still be locked briefly)
set /a R=0
:retry
if %R% GEQ 10 (
    echo [sfc-update] ERROR: could not delete old executable after 10 tries.
    pause
    goto end
)
del /f "%TARGET%" 2>NUL
if exist "%TARGET%" (
    set /a R+=1
    timeout /t 1 /nobreak >NUL
    goto retry
)

move /y "%NEW%" "%TARGET%"
if errorlevel 1 (
    echo [sfc-update] ERROR: move failed.
    pause
    goto end
)

echo [sfc-update] Update complete. Launching new version...
start "" "%TARGET%"

:end
:: Self-delete this batch script
(goto) 2>nul & del /f /q "%~f0"
"""


def _launch_bat(exe: Path, new_data: bytes) -> UpdateApplyResult:
    """Write new binary to temp, launch a detached .bat that:
    1. Waits 2 seconds
    2. Deletes old .exe (retry loop)
    3. Moves new .exe into place
    4. Launches the new .exe
    5. Deletes itself
    """
    new_file = exe.parent / f".sfc_update_{os.getpid()}.exe"
    bat_file = exe.parent / f".sfc_update_{os.getpid()}.bat"

    try:
        new_file.write_bytes(new_data)
    except OSError as e:
        return UpdateApplyResult(False, f"write failed: {e}")

    bat_content = _BAT.format(target=str(exe), new_file=str(new_file))
    try:
        bat_file.write_text(bat_content, encoding="utf-8")
    except OSError as e:
        new_file.unlink(missing_ok=True)
        return UpdateApplyResult(False, f"bat write failed: {e}")

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
    except OSError as e:
        new_file.unlink(missing_ok=True)
        bat_file.unlink(missing_ok=True)
        return UpdateApplyResult(False, f"failed to launch updater: {e}")

    return UpdateApplyResult(
        True,
        "Update downloaded. sfc will close now.\n"
        "The updater will replace the .exe and relaunch automatically.",
    )


# ════════════════════════════════════════════════════════════════════
#  PUBLIC API
# ════════════════════════════════════════════════════════════════════

def check_update() -> UpdateCheckResult:
    """Fetch ``version.py`` from raw GitHub, compare versions."""
    try:
        raw = _fetch(_VERSION_URL)
    except (URLError, OSError, TimeoutError) as e:
        return UpdateCheckResult(False, "", VERSION, f"network error: {e}")

    remote = _parse_remote_version(raw)
    if not remote:
        return UpdateCheckResult(False, "", VERSION, "could not parse remote version")

    return UpdateCheckResult(
        available=_is_newer(remote, VERSION),
        remote_version=remote,
        current_version=VERSION,
        error="",
    )


def apply_update() -> UpdateApplyResult:
    """Download latest version and overwrite current executable.

    Pipeline per exe kind:

    ``package``
        Overwrite each module file from GITHUB_RAW_BASE.

    ``zipapp``
        Download ``sfc.pyz`` from Releases. Fallback: package mode.

    ``exe`` (Windows)
        Download ``sfc.exe`` from Releases → temp file → detached .bat
        waits 2s, swaps, relaunches, self-deletes.

    ``elf`` (Linux/macOS)
        Download binary from Releases → ``os.replace()`` (atomic on POSIX).
    """
    exe = _exe_path()
    kind = _detect_kind(exe)

    if not _is_writable(exe):
        return UpdateApplyResult(False, f"no write permission: {exe}")

    try:
        if kind == _Kind.PACKAGE:
            return _up_package(exe)
        if kind == _Kind.ZIPAPP:
            return _up_zipapp(exe)
        if kind == _Kind.EXE:
            return _up_exe(exe)
        if kind == _Kind.ELF:
            return _up_elf(exe)
        return _up_package(exe)
    except Exception as e:
        return UpdateApplyResult(False, f"update failed: {e}")


# ── Per-kind implementations ────────────────────────────────────────

def _up_package(exe: Path) -> UpdateApplyResult:
    pkg = exe.parent if exe.parent.name == "sfc" else exe.parent / "sfc"
    if not pkg.is_dir():
        return UpdateApplyResult(False, f"package dir not found: {pkg}")

    ok = 0
    errs: list[str] = []
    for rel in _PACKAGE_FILES:
        url = f"{GITHUB_RAW_BASE}/sfc/{rel}"
        tgt = pkg / rel
        try:
            data = _fetch(url)
        except (URLError, OSError) as e:
            errs.append(f"{rel}: {e}")
            continue
        tgt.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write(tgt, data)
        ok += 1

    if ok == 0:
        return UpdateApplyResult(False, f"no files updated: {'; '.join(errs)}")
    msg = f"updated {ok}/{len(_PACKAGE_FILES)} files — please restart sfc"
    if errs:
        msg += f"\n⚠️ skipped: {len(errs)} file(s)"
    return UpdateApplyResult(True, msg)


def _up_zipapp(exe: Path) -> UpdateApplyResult:
    url = _get_asset_url("sfc.pyz")
    if url:
        try:
            data = _fetch(url)
            _atomic_write(exe, data)
            if os.name != "nt":
                exe.chmod(
                    exe.stat().st_mode
                    | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH,
                )
            return UpdateApplyResult(True, f"updated {exe.name} — please restart sfc")
        except (URLError, OSError):
            pass
    return _up_package(exe)


def _up_exe(exe: Path) -> UpdateApplyResult:
    url = _get_asset_url("sfc.exe")
    if not url:
        return UpdateApplyResult(False, "sfc.exe not found in GitHub release assets")
    try:
        data = _fetch(url)
    except (URLError, OSError) as e:
        return UpdateApplyResult(False, f"download failed: {e}")
    if len(data) < 1024:
        return UpdateApplyResult(False, "downloaded file too small — not a valid binary")
    return _launch_bat(exe, data)


def _up_elf(exe: Path) -> UpdateApplyResult:
    hint = "sfc-macos" if sys.platform == "darwin" else "sfc-linux"
    url = _get_asset_url(hint) or _get_asset_url("sfc")
    if not url:
        return UpdateApplyResult(False, "binary asset not found in GitHub release")
    try:
        data = _fetch(url)
    except (URLError, OSError) as e:
        return UpdateApplyResult(False, f"download failed: {e}")
    if len(data) < 1024:
        return UpdateApplyResult(False, "downloaded file too small — not a valid binary")

    # POSIX: os.replace works even on running binaries
    _atomic_write(exe, data)
    try:
        exe.chmod(
            exe.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH,
        )
    except OSError:
        pass
    return UpdateApplyResult(True, f"updated {exe.name} — please restart sfc")