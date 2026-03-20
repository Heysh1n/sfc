# 🔧 Smart File Collector (sfc)

A zero-dependency CLI/TUI tool that collects project source code into a single
structured text file — built specifically for feeding codebases into AI chats
(ChatGPT, Claude, Gemini).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#)
[![Version](https://img.shields.io/badge/version-4.0.0-cyan.svg)](#)

---

## The Problem

Manually copying dozens of source files into an AI chat is painful:

- 📁 Project structure context is lost
- 🗑️ Junk files (`.git`, `node_modules`, `.env`) pollute the context
- ✂️ Character limits break long messages
- ⏱️ The whole process takes forever

## The Solution

```bash
python -m sfc
# → Interactive TUI opens
# → Select files with arrow keys + space
# → Press Enter → structured output + clipboard
```

One command. Smart filtering. Auto-split. Clipboard copy. Done.

---

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Zero dependencies** | Pure Python 3.10+ stdlib. No runtime pip dependencies needed. |
| **Cross-platform** | Linux, macOS, Windows. Native TUI on all three. |
| **Interactive TUI** | Arrow-key navigation, checkboxes, scrollable lists via `curses`/`msvcrt`. |
| **Smart ignoring** | Built-in ignore rules. Fully customisable in Settings. |
| **Auto-split** | Splits output into parts when exceeding character limits. |
| **Native clipboard** | `pbcopy` · `clip.exe` · `wl-copy` · `xclip` · `xsel` — no pyperclip. |
| **Presets** | Save & reuse file selections per project. |
| **Self-updater** | Update raw package files, `.pyz`, and compiled binaries from GitHub. |
| **Persistent config** | Settings saved to `~/.config/sfc/cfg.setting.json`. |
| **Dynamic collect** | Uncheck files in the final review before generating output. |
| **Comment Killer** | AST-based stripping of Python docstrings and `#` comments before export. |
| **Portable zipapp** | Build `dist/sfc.pyz` with native Python `zipapp`. |

---

## 📦 Installation

### Quick (any OS)

```bash
git clone https://github.com/Heysh1n/sfc.git
cd sfc
python -m sfc
```

### Linux / macOS

```bash
# Run directly
python3 -m sfc

# Build a portable single-file archive
make zipapp
./dist/sfc.pyz

# Or
python3 build.py
./dist/sfc.pyz
```

**Install globally:**

```bash
cp dist/sfc.pyz ~/.local/bin/sfc
chmod +x ~/.local/bin/sfc
sfc
```

**Clipboard (Linux only):**

```bash
# Wayland
sudo apt install wl-clipboard

# X11
sudo apt install xclip
```

### Windows

```powershell
python -m sfc

# Build zipapp
python build.py
python dist\sfc.pyz
```

Clipboard works automatically via `clip.exe`.

---

## 🚀 Quick Start

### Interactive Mode (TUI)

```bash
python -m sfc
```

Opens a full-screen terminal interface:

```text
  ━━━ 🔧 Smart File Collector v4.0.0 ━━━
  📂 Project: sfc  │  📄 Files: 19
────────────────────────────────────────────────────────────
 ▸ 📂  Browse & Select
   🔍  Search by pattern
   📝  Quick pick (paste paths)
   📋  Collect ALL files
   🔖  Presets
   🗂️   View tree
   ⚙️   Settings
   📖  Help
   🔄  Check for updates
   ──────────────────────────────
   ✅  Collect selected (0)
   👁️   Preview selected
   🗑️   Clear selection
   ──────────────────────────────
   ❌  Exit

   ↑↓:navigate  ENTER:select  q:quit
 Made with ❤️ by Heysh1n
```

**Controls:**

| Key | Action |
|-----|--------|
| ↑ / ↓ | Navigate |
| SPACE | Toggle checkbox |
| ENTER | Select / confirm |
| ESC | Go back |
| q | Quit |

### CLI Mode (Scripting)

```bash
# Collect everything
sfc all -o context.txt

# Pick specific files or patterns
sfc pick src/main.py "src/config/*" "*.json"

# Strip Python comments/docstrings during collect
sfc all --strip

# Show tree with sizes
sfc tree -s

# Find files
sfc find "*.service.ts"

# Read paths from file
sfc from paths.txt

# Manage presets
sfc preset save backend "src/models/*" "src/db/*"
sfc preset backend
sfc preset list
```

---

## 🎯 CLI Reference

### Commands

| Command | Description |
|---------|-------------|
| *(none)* | Launch interactive TUI |
| `all` | Collect all project files |
| `pick [files...]` | Collect by path or glob pattern |
| `pick -` | Interactive multi-line path input |
| `tree` | Display project structure |
| `find <pattern>` | Find files matching a glob |
| `from <file>` | Read paths from a text file |
| `preset <action>` | Save / load / delete presets |

### Flags

| Flag | Description | Default |
|------|-------------|---------|
| `-p, --path` | Target root directory | `.` |
| `-o, --output` | Output filename | `collected_output.txt` |
| `-c, --chars` | Max chars per part | `90000` |
| `--no-tree` | Exclude tree from output | off |
| `-i, --ignore` | Extra dirs to ignore | `[]` |
| `--strip` | Strip docstrings/comments from `.py` files | config value |
| `-V, --version` | Print version | — |

---

## 🎮 TUI Screens

### Browse & Select

Select individual files with checkboxes:

| Key | Action |
|-----|--------|
| SPACE | Toggle file checkbox |
| / | Filter by substring |
| a | Select all visible |
| n | Deselect all visible |
| p | Select by glob pattern |
| c | Clear filter |
| ENTER | Done → back to menu |

### Collect Flow

Before generating output, a **review screen** lets you dynamically
uncheck files:

```text
  ━━━ 🔧 Smart File Collector v4.0.0 ━━━
  ✅ Collect — 5 files
  Uncheck items to exclude before collecting
────────────────────────────────────────────────────────────
 [x] src/main.py
 [x] src/config/settings.py
 [ ] src/tests/test_main.py
 [x] README.md
 [x] pyproject.toml

   SPACE:toggle  ENTER:collect  ESC:cancel
 Made with ❤️ by Heysh1n
```

### Settings

Persistent configuration with editable options:

```text
  ━━━ 🔧 Smart File Collector v4.0.0 ━━━
  ⚙️ Settings
────────────────────────────────────────────────────────────
 ▸ Output file:        collected_output.txt
   Max chars/part:     90,000
   Include tree:       ON
   Auto clipboard:     OFF
   Page size:          20
   Comment Killer:     OFF
   Clipboard backend:  xclip
   ──────────────────────────────
   🚫  Ignoring (dirs/files/ext)
   🔄  Refresh files  (19 indexed)
   ──────────────────────────────
   ↩   Back

   ↑↓:navigate  ENTER:select  q:quit
 Made with ❤️ by Heysh1n
```

- **Settings → Ignoring → Directories** — folder names to skip
- **Settings → Ignoring → Files** — exact filenames to skip
- **Settings → Ignoring → Extensions** — suffixes to skip
- **Reset to defaults** — restore built-in rules

Config saved at:

| OS | Path |
|----|------|
| Linux/macOS | `~/.config/sfc/cfg.setting.json` |
| Windows | `%APPDATA%\sfc\cfg.setting.json` |

---

## 💀 Comment Killer (v4.0)

`Smart File Collector` can now strip Python explanations before export.

When enabled:

- Module docstrings are removed
- Class docstrings are removed
- Function docstrings are removed
- `#` comments are removed
- Common pragmas are preserved:
  - `# type:`, `# noqa`, `# pragma:`, `# pylint:`
  - `# fmt:`, `# isort:`, `# mypy:`, `# pyright:`

Implemented with `ast` + `tokenize`. **No regex is used.**

Enable it via:

- **TUI:** `Settings → Comment Killer`
- **CLI:** `--strip`

---

## 📄 Output Format

```text
══════════════
📋 sfc [pick]
📅 19.03.2026 16:52:42
📄 Files: 3
══════════════

┌────────────
│ 🗂️  STRUCTURE
├────────────
│ 📦 sfc/
│ ├── 📂 src/
│ │   ├── 📄 main.py
│ │   └── 📄 utils.py
│ └── 📄 README.md
└────────────

┌─── 📄 [1/3] src/main.py
def main():
    print("Hello AI!")
└────────────────────────────────────────

┌─── 📄 [2/3] src/utils.py
def helper():
    return 42
└────────────────────────────────────────

┌─── 📄 [3/3] README.md
# My Project
└────────────────────────────────────────

═════
✅ End
═════
```

**Auto-split:** When output exceeds the character limit, files are
automatically split into `_p1.txt`, `_p2.txt`, etc.

---

## 🔖 Presets

Save file selections for repeated use:

```bash
# Save
sfc preset save api "src/routes/*" "src/middleware/*"

# Use
sfc preset api

# List
sfc preset list

# Delete
sfc preset delete api
```

Stored per-project in `.sfc-presets.json`.

---

## 🔄 Self-Updater

In TUI: **Main Menu → Check for updates**

v4.0 updater supports:

| Format | Method |
|--------|--------|
| Package (`python -m sfc`) | Overwrites individual module files |
| Zipapp (`.pyz`) | Downloads asset from GitHub Releases |
| Windows `.exe` | Detached batch-script swaps running binary |
| Linux/macOS binary | Atomic rename (POSIX doesn't lock executables) |

No sudo required unless installed in a protected system directory.

---

## 🏗️ Architecture

```text
sfc/
├── Makefile             # zipapp / win / linux / macos / check / clean
├── build.py             # Python-native build script
├── pyproject.toml       # Package metadata
├── requirements-build.txt
└── sfc/
    ├── __init__.py      # Package marker
    ├── __main__.py      # Entry point
    ├── version.py       # Version + metadata constants
    ├── patterns.py      # Default ignores, glob helpers
    ├── config.py        # Persistent JSON config
    ├── collector.py     # File scanner, AST comment killer, tree, output
    ├── clipboard.py     # Native clipboard integration
    ├── updater.py       # Self-update (package / pyz / exe / elf)
    ├── app.py           # CLI parser + TUI controller
    └── tui/
        ├── __init__.py  # Platform detection
        ├── base.py      # Key enum, abstract engine, menu_loop
        ├── curses_tui.py # Linux/macOS engine
        └── win_tui.py   # Windows engine
```

**Zero** runtime dependencies.
**Zero** circular imports.

---

## 📋 Requirements

- Python 3.10+
- Terminal with at least 80×24 for TUI
- **Linux clipboard:** `xclip`, `xsel`, or `wl-copy`
- **macOS clipboard:** built-in (`pbcopy`)
- **Windows clipboard:** built-in (`clip.exe`)

---

## 🔨 Building

### Portable zipapp

```bash
make zipapp
# or
python build.py
```

Output: `dist/sfc.pyz`

```bash
./dist/sfc.pyz        # Linux/macOS
python dist\sfc.pyz   # Windows
```

### PyInstaller binaries

```bash
make check    # verify prerequisites first
make win      # Windows .exe
make linux    # Linux ELF
make macos    # macOS binary
```

> **Note:** PyInstaller requires Python built with `--enable-shared`.
> GitHub Codespaces does not have this. Use `make zipapp` instead.

### Clean

```bash
make clean
# or
python build.py clean
```

---

## 💡 Tips for AI Workflows

1. **Don't send everything.**
   ```bash
   sfc pick "src/db/*" "src/models/*"
   ```

2. **Use character limits.**
   ```bash
   sfc all -c 50000
   ```

3. **Strip comments for cleaner Python context.**
   ```bash
   sfc all --strip
   ```

4. **Quick Pick from AI output.**
   Copy the list → TUI → Quick Pick → paste → collect.

5. **Combine with git:**
   ```bash
   git diff --name-only > changed.txt
   sfc from changed.txt
   ```

6. **Save frequent selections:**
   ```bash
   sfc preset save backend "src/models/*" "src/services/*"
   ```

---

## 📜 License

[MIT](LICENSE) — © 2026 [Heysh1n](https://github.com/Heysh1n)

Made with ❤️ by Heysh1n