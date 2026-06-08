## [4.9.0] - 2026-06-08
### Added
- **Silent Updater**: Added a non-blocking background update check at TUI startup.
- **Update Banner**: The main menu now shows an unobtrusive update notice when a newer GitHub release is available.
- **Installer Version Picker**: The interactive installer can now install either the latest release or a specific version tag.
- **Uninstall Target**: Added `make uninstall` and an installer uninstall action for removing `~/.local/bin/sfc`.

### Changed
- **TUI Input Loop**: Added short timed key polling for the main menu so update notices can appear without waiting for a key press.

### Fixed
- **Offline Startup**: GitHub update checks now use a short timeout and silently ignore network/API failures, so startup remains instant and stable without internet.

## [4.8.0] - 2026-06-03
### Added
- **Root Guard**: Prevented accidental scanning of root (`/`) and home (`~`) directories.
- **Binary Guard**: Added heuristic `\x00` byte detection to skip binary/media files and prevent memory bloat.
- **Max Files Limit**: Hard-capped directory traversal at 50,000 files to prevent OOM kills.
- **Local Config**: Added support for project-specific `.sfcignore` files.

### Fixed
- **Graceful Exit**: Suppressed raw Python tracebacks on `Ctrl+C` (KeyboardInterrupt), ensuring clean exit code 130 and terminal state restoration.
