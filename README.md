# 🔧 Smart File Collector (sfc) [ARCHIVED]

> **⚠️ NOTICE: Active development has moved to SFCP (Smart File Collector PRO).**
> Version 4.9.0 is the final, rock-solid release of the free open-source core. 

A zero-dependency CLI/TUI tool that collects project source code into a single
structured text file — built specifically for feeding codebases into AI chats
(ChatGPT, Claude, Gemini).

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://python.org)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Zero Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#)
[![Version](https://img.shields.io/badge/version-4.9.0-cyan.svg)](#)
[![Status](https://img.shields.io/badge/status-archived-red.svg)](#)

---

## 💎 Introducing SFCP (Smart File Collector PRO)

Why archived? Honestly, I'm a university student, and tuition bills don't pay themselves. 😅 

I've built a massive upgrade called **SFCP**. It receives daily updates, premium support, and transforms this simple collector into a bi-directional AI workflow engine. 

**Exclusive SFCP Features:**
* **`sfcp scaffold`**: Feed it an ASCII tree from ChatGPT, and it automatically builds the folder/file structure on your disk.
* **Smart Export Formats**: Export code directly to valid Markdown or JSON payloads for API integrations.
* **Safe-Mode Environment**: Includes your `.env` structure but scrubs the actual secrets (`DB_PASS=***REDACTED***`).
* **Regex Mass Rename**: Bulk file renaming built specifically to respect AI-generated restructuring.
* **Windows Native Integration**: Right-click any folder in Windows Explorer -> "Collect with SFCP" + one-line PowerShell install.
* **Prompt Engine**: Built-in developer prompt generation on the fly.

**👉 [Get SFCP here (Support a student!)](heysh1n.com.tr)**

---

## The Problem

Manually copying dozens of source files into an AI chat is painful:

- 📁 Project structure context is lost
- 🗑️ Junk files (`.git`, `node_modules`, `.env`) pollute the context
- ✂️ Character limits break long messages
- ⏱️ The whole process takes forever

## The Solution

```bash
sfc
# → Interactive TUI opens
# → Select files with arrow keys + space
# → Press Enter → structured output + clipboard


```

One command. Smart filtering. Auto-split. Clipboard copy. Done.

---

## ✨ Features

| Feature | Description |
| --- | --- |
| **Zero dependencies** | Pure Python 3.10+ stdlib. No runtime pip dependencies needed. |
| **Cross-platform** | Linux, macOS, Windows. Native TUI on all three. |
| **Interactive TUI** | Arrow-key navigation, checkboxes, scrollable lists via `curses`/`msvcrt`. |
| **Smart ignoring** | Built-in ignore rules. Fully customisable in Settings. |
| **Stability Guards** | Hard-capped directory traversal and binary file skipping. |
| **Silent Updater** | Asynchronous background update checking without freezing the TUI. |
| **Project Size Report** | Displays total project size and percentage weight of dependency folders. |
| **Limited-Depth Tree** | Truncate tree output with `-l` and automatically calculate skipped folder contents. |
| **Auto-split** | Splits output into parts when exceeding character limits. |
| **Native clipboard** | `pbcopy` · `clip.exe` · `wl-copy` · `xclip` · `xsel` — no pyperclip. |
| **Presets** | Save & reuse file selections per project. |
| **Dynamic Self-Updater** | Pulls latest `sfc.pyz` release binaries directly from GitHub API. |
| **Persistent config** | Settings saved to `~/.config/sfc/cfg.setting.json`. |
| **Comment Killer** | AST-based stripping of Python docstrings and `#` comments before export. |
| **Portable zipapp** | Build dynamic `sfc.pyz` containing the native package structure. |

---

## 📦 Installation

### One-line Install (Linux / macOS)

```bash
sh -c "$(curl -fsSL [https://raw.githubusercontent.com/Heysh1n/sfc/main/install.sh](https://raw.githubusercontent.com/Heysh1n/sfc/main/install.sh))"

```

The installer can fetch the latest GitHub Release or a specific release tag from `Heysh1n/sfc`, parses the `sfc.pyz` asset, installs it directly to `~/.local/bin/sfc` and marks it executable.

### From Source

```bash
git clone [https://github.com/Heysh1n/sfc.git](https://github.com/Heysh1n/sfc.git)
cd sfc
python3 -m sfc


```

### Using Makefile (Linux / macOS)

```bash
# Build a portable single-file archive (sfc.pyz)
make build

# Install globally to ~/.local/bin/sfc
make local-install

# Remove ~/.local/bin/sfc
make uninstall


```

**Clipboard Prerequisites (Linux only):**

```bash
# Wayland
sudo apt install wl-clipboard
# X11
sudo apt install xclip


```

### Windows

```powershell
python -m sfc

# Build zipapp manually
python build.py
python sfc.pyz


```

---

## 🚀 Quick Start

### Interactive Mode (TUI)

```bash
sfc
# or if running raw source: python3 -m sfc


```

Opens a full-screen terminal interface:

```text
  ━━━ 🔧 Smart File Collector v4.9.0 ━━━
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

---

## 📊 Size Report

CLI analysis automatically runs and prints project sizes before command output execution:

```text
Total project size: 14.2M
Dependency [node_modules]: 8.4M (59.1%)
Dependency [.venv]: 3.1M (21.8%)


```

Detected first-level dependency/build folders include: `node_modules`, `venv`, `.venv`, `target`, and `build`. All percentages are dynamically calculated relative to total directory size via `Path.rglob()`.

---

## 🎯 CLI Reference

### Commands

| Command | Description |
| --- | --- |
| *(none)* | Launch interactive TUI |
| `all` | Collect all project files |
| `pick [files...]` | Collect by path or glob pattern |
| `pick -` | Interactive multi-line path input |
| `tree` | Display project structure |
| `find <pattern>` | Find files matching a glob |
| `from <file>` | Read paths from a text file |
| `preset <action>` | Save / load / delete presets |
| `--update` | Trigger dynamic self-updater via GitHub API |

### Flags

| Flag | Description | Default |
| --- | --- | --- |
| `-p, --path` | Target root directory | `.` |
| `-o, --output` | Output filename | `collected_output.txt` |
| `-c, --chars` | Max chars per part | `90000` |
| `-l, --level` | Max directory depth limit for `tree` | Full depth |
| `--no-tree` | Exclude tree from output | off |
| `-i, --ignore` | Extra dirs to ignore | `[]` |
| `--strip` | Strip docstrings/comments from `.py` files | config value |
| `-V, --version` | Print version | — |

---

## 🗂️ Tree Depth Limitation

Use `-l` / `--level` to prevent long terminal or context spans when running project trees:

```bash
sfc tree -l 1
sfc tree --level 2


```

When a directory layer reaches the limit, `sfc` stops traversing deeper and leverages `Path.rglob()` to print a condensed summary:

```text
📦 my-project/
├── 📂 node_modules/ (+1,842 folders | +12,450 files)
├── 📂 sfc/ (+8 folders | +64 files)
├── 📂 tests/ (+2 folders | +18 files)
├── 📂 docs/ (empty)
├── 📄 README.md
└── 📄 pyproject.toml


```

---

## 💀 Comment Killer

`sfc` strips down Python explanations via `ast` + `tokenize` processing to save LLM tokens.

When enabled (`--strip` or via TUI Settings), it wipes:

* Module, Class, and Function docstrings.
* All standard `#` comments.
* **Preserves code pragmas:** `# type:`, `# noqa`, `# pragma:`, `# pylint:`, `# fmt:`, etc.

---

## 🔄 Self-Updater Engine

```bash
sfc --update


```

The dynamic updater executes under the following flow:

1. Queries the GitHub API: `https://api.github.com/repos/Heysh1n/sfc/releases/latest` using a mandatory `User-Agent: sfc-updater` header.
2. Extracts `tag_name`, automatically stripping any `v` prefix (`v4.9.0` -> `4.9.0`).
3. Formats versions into integer tuples to perform strict SemVer comparison (`4.10.0` > `4.9.0`).
4. Locates the `sfc.pyz` build asset, downloads it into a localized `<current-binary>.tmp` file, and uses an atomic `os.replace()` swap before applying executable permissions (`0o755`).

---

## 🏗️ Architecture

```text
sfc/
├── Makefile             # build (zipapp) / local-install / clean
├── build.py             # Python-native build script
├── install.sh           # Interactive TUI bash installation script
├── pyproject.toml       # Package metadata (Poetry managed)
├── poetry.lock          # Locked dependency states
└── sfc/
    ├── __init__.py      # Package marker
    ├── __main__.py      # Entry point (main:cli mapping)
    ├── version.py       # Version storage (__version__ = "4.9.0")
    ├── patterns.py      # Default ignores, glob helpers
    ├── config.py        # Persistent JSON config
    ├── collector.py     # File scanner, AST comment killer, tree, sizes
    ├── clipboard.py     # Native clipboard integration
    ├── updater.py       # GitHub API SemVer self-update logic
    ├── app.py           # CLI parser + TUI controller
    └── tui/
        ├── __init__.py  # Platform detection
        ├── base.py      # Key enum, abstract engine, menu_loop
        ├── curses_tui.py # Linux/macOS engine
        └── win_tui.py   # Windows engine


```

---

## 📜 License

[MIT](https://www.google.com/search?q=LICENSE) — © 2026 [Heysh1n](https://github.com/Heysh1n)

<p align="center">
  Made with ❤️ by Heysh1n
</p>
