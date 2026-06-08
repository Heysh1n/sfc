"""Self-updater based on the latest GitHub Release asset."""

from __future__ import annotations

import json
import os
import stat
import sys
import threading
import urllib.request
from pathlib import Path
from typing import Any, NamedTuple
from urllib.error import URLError

from sfc.version import __version__


class UpdateCheckResult(NamedTuple):
    available: bool
    remote_version: str
    current_version: str
    error: str


class UpdateApplyResult(NamedTuple):
    ok: bool
    message: str


_TIMEOUT: int = 20
_BACKGROUND_TIMEOUT: float = 1.5
GITHUB_RELEASES_API: str = "https://api.github.com/repos/Heysh1n/sfc/releases/latest"
_ASSET_NAME: str = "sfc.pyz"
_USER_AGENT: str = "sfc-updater"
_BACKGROUND_UPDATE_VERSION: str = ""
_BACKGROUND_UPDATE_DONE: bool = False
_BACKGROUND_UPDATE_LOCK = threading.Lock()


def _request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"User-Agent": _USER_AGENT})


def _fetch_json(url: str, timeout: float = _TIMEOUT) -> dict[str, Any]:
    with urllib.request.urlopen(_request(url), timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        raise ValueError("GitHub API returned non-object JSON")
    return data


def _normalize_version(version: str) -> str:
    return version.strip().lstrip("v")


def _version_tuple(version: str) -> tuple[int, ...]:
    return tuple(map(int, _normalize_version(version).split(".")))


def _is_newer(remote: str, local: str) -> bool:
    return _version_tuple(remote) > _version_tuple(local)


def _asset_url(release: dict[str, Any], asset_name: str = _ASSET_NAME) -> str:
    assets = release.get("assets", [])
    if not isinstance(assets, list):
        return ""

    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if asset.get("name") == asset_name:
            url = asset.get("browser_download_url", "")
            return url if isinstance(url, str) else ""
    return ""


def _current_binary() -> Path:
    if not sys.argv or not sys.argv[0]:
        raise RuntimeError("cannot detect current executable path")
    return Path(sys.argv[0]).expanduser().resolve()


def _download_to_tmp(url: str, tmp: Path) -> None:
    with urllib.request.urlopen(_request(url), timeout=_TIMEOUT) as resp:
        with tmp.open("wb") as fh:
            while True:
                chunk = resp.read(1024 * 64)
                if not chunk:
                    break
                fh.write(chunk)

    if tmp.stat().st_size == 0:
        raise RuntimeError("downloaded asset is empty")


def _chmod_executable(path: Path) -> None:
    mode = path.stat().st_mode
    path.chmod(mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


def check_update() -> UpdateCheckResult:
    try:
        release = _fetch_json(GITHUB_RELEASES_API)
        remote = str(release.get("tag_name", "")).strip()
    except (URLError, OSError, TimeoutError, ValueError, json.JSONDecodeError) as exc:
        return UpdateCheckResult(False, "", __version__, f"network error: {exc}")

    if not remote:
        return UpdateCheckResult(False, "", __version__, "GitHub release has no tag_name")

    return UpdateCheckResult(
        available=_is_newer(remote, __version__),
        remote_version=remote,
        current_version=__version__,
        error="",
    )


def check_update_background() -> None:
    """Silently check the latest release and cache its version if newer."""
    global _BACKGROUND_UPDATE_DONE, _BACKGROUND_UPDATE_VERSION

    try:
        release = _fetch_json(GITHUB_RELEASES_API, timeout=_BACKGROUND_TIMEOUT)
        remote = str(release.get("tag_name", "")).strip()
        if remote and _is_newer(remote, __version__):
            with _BACKGROUND_UPDATE_LOCK:
                _BACKGROUND_UPDATE_VERSION = remote
    except Exception:
        pass
    finally:
        with _BACKGROUND_UPDATE_LOCK:
            _BACKGROUND_UPDATE_DONE = True


def get_background_update_version() -> str:
    """Return the cached newer release version found by the background check."""
    with _BACKGROUND_UPDATE_LOCK:
        return _BACKGROUND_UPDATE_VERSION


def is_background_update_check_done() -> bool:
    """Return whether the background update check has finished."""
    with _BACKGROUND_UPDATE_LOCK:
        return _BACKGROUND_UPDATE_DONE


def self_update() -> UpdateApplyResult:
    try:
        release = _fetch_json(GITHUB_RELEASES_API)
        remote = str(release.get("tag_name", "")).strip()
        if not remote:
            return UpdateApplyResult(False, "GitHub release has no tag_name")

        if not _is_newer(remote, __version__):
            return UpdateApplyResult(True, f"already up to date ({__version__})")

        download_url = _asset_url(release)
        if not download_url:
            return UpdateApplyResult(False, f"{_ASSET_NAME} not found in latest release")

        target = _current_binary()
        tmp = Path(str(target) + ".tmp")
        tmp.unlink(missing_ok=True)

        try:
            _download_to_tmp(download_url, tmp)
            os.replace(tmp, target)
            _chmod_executable(target)
        finally:
            tmp.unlink(missing_ok=True)

        return UpdateApplyResult(True, f"updated to {remote}")
    except Exception as exc:
        return UpdateApplyResult(False, f"update failed: {exc}")


def update_current_binary() -> UpdateApplyResult:
    return self_update()


def apply_update() -> UpdateApplyResult:
    return self_update()
