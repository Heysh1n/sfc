## [4.8.0] - 2026-06-03
### Added
- **Root Guard**: Prevented accidental scanning of root (`/`) and home (`~`) directories.
- **Binary Guard**: Added heuristic `\x00` byte detection to skip binary/media files and prevent memory bloat.
- **Max Files Limit**: Hard-capped directory traversal at 50,000 files to prevent OOM kills.
- **Local Config**: Added support for project-specific `.sfcignore` files.

### Fixed
- **Graceful Exit**: Suppressed raw Python tracebacks on `Ctrl+C` (KeyboardInterrupt), ensuring clean exit code 130 and terminal state restoration.