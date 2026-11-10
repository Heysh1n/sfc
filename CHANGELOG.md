# Changelog

## [Unreleased]

### Fixed
- `sfc all` and `sfc tree` no longer crash with "Limit of N files reached" on large monorepos.
- Directory scans no longer descend into `node_modules`, `.venv`, `target`, `.git` and other dependency or artifact folders before the ignore rules are applied.
- `sfc tree --level N` now stops at the depth limit and prints the directory name. It no longer runs a recursive count of the files and folders inside.

### Changed
- File discovery and the project size report use `os.walk(topdown=True)`. Ignored directories are removed from `dirs[:]` before descent.
- The tree is generated lazily with `os.scandir` and an explicit stack, so it uses no recursion and builds no full-tree structure.
- Hidden directories (names starting with `.`) and symlinked directories are skipped during traversal.
- The default ignore set always applies, even when a saved config predates it. It now also includes `target`, `vendor`, `bin` and `obj`.
- The project size report covers visible files only. Dependency folders are listed as `skipped (ignored, not scanned)` and no longer show a size or percentage.

### Removed
- The hard file-count limit. `MaxFilesLimitError` is no longer raised and is kept only for import compatibility. The `max_files_limit` config option is now unused.
- The `Path.rglob()` helpers `_sum_files_rglob`, `_count_nested_entries` and `_limited_dir_label`.

### Notes
- Still pure Python 3.10+ standard library, with no new dependencies.
