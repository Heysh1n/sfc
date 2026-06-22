from __future__ import annotations

import argparse
import platform
import subprocess
import sys
import threading
from pathlib import Path

from sfc.version import VERSION, APP_TITLE
from sfc.config import AppConfig, load_config, save_config, load_presets, save_presets
from sfc.collector import (
    MaxFilesLimitError,
    get_all_files,
    build_tree,
    write_output,
    fmt_size,
    project_size_report,
)
from sfc.clipboard import copy_to_clipboard, available_backend, ClipboardResult
from sfc.patterns import (
    resolve_patterns,
    matches_pattern,
    HELP_GLOB,
    HELP_PRESETS,
    HELP_FILTERS,
)
from sfc.updater import (
    apply_update,
    check_update,
    check_update_background,
    get_background_update_version,
    is_background_update_check_done,
    update_current_binary,
)


STOPPED_BY_USER_MESSAGE: str = "\n[!] Stopped by user"
ROOT_GUARD_MESSAGE: str = (
    "[!] ERROR: Refusing to scan root or home directory to prevent system hang. "
    "Use specific project folders."
)
_BACKGROUND_UPDATE_THREAD_STARTED: bool = False
_BACKGROUND_UPDATE_THREAD_LOCK = threading.Lock()


# ════════════════════════════════════════════════════════════════════
#  SFC PRO AD BANNER
# ════════════════════════════════════════════════════════════════════

_SFC_PRO_BANNER: str = """\
\033[93m╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║   ⭐  SFC PRO — Smart File Collector for Teams              ║
║                                                              ║
║   🚀 Unlimited file limits      🔒 Encrypted output         ║
║   ☁️  Cloud sync & sharing      📊 Analytics dashboard      ║
║   🤖 AI-powered file selection  🔧 Priority support         ║
║                                                              ║
║   Upgrade today → https://github.com/Heysh1n/sfc-pro        ║
║                                                              ║
╚══════════════════════════════════════════════════════════════╝\033[0m
"""


def _show_ad_banner(cfg: AppConfig) -> None:
    """Display the SFC PRO advertisement banner if not disabled."""
    if not cfg.show_ads:
        return
    print(_SFC_PRO_BANNER)
    try:
        answer = input("  Press Enter to continue or X to close ad: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if answer == "x":
        return


def _is_version_below_5(version: str) -> bool:
    """Return True if *version* is older than 5.0.0."""
    try:
        parts = version.strip().lstrip("v").split(".")
        return int(parts[0]) < 5
    except (ValueError, IndexError):
        return False


def _exit_stopped_by_user() -> None:
    print(STOPPED_BY_USER_MESSAGE, file=sys.stderr)
    sys.exit(130)


def _resolve_target_path(target_path: str | Path) -> Path:
    resolved = Path(target_path).expanduser().resolve()
    home = Path.home().resolve()

    if (
        resolved == home
        or resolved == Path("/").resolve()
        or resolved == resolved.parent
    ):
        print(ROOT_GUARD_MESSAGE, file=sys.stderr)
        sys.exit(1)

    return resolved


def _start_background_update_check() -> None:
    """Launch the silent update check once for interactive TUI sessions."""
    global _BACKGROUND_UPDATE_THREAD_STARTED

    with _BACKGROUND_UPDATE_THREAD_LOCK:
        if _BACKGROUND_UPDATE_THREAD_STARTED:
            return
        _BACKGROUND_UPDATE_THREAD_STARTED = True

    try:
        thread = threading.Thread(
            target=check_update_background,
            name="sfc-update-check",
            daemon=True,
        )
        thread.start()
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
#  CLI (NON-INTERACTIVE) COMMANDS
# ════════════════════════════════════════════════════════════════════

def _cli_all(args: argparse.Namespace, cfg: AppConfig) -> None:
    root = _resolve_target_path(args.path)
    if not root.is_dir():
        print(f"❌ Not a directory: {root}")
        return
    extra = set(args.ignore) if args.ignore else None
    files = get_all_files(root, cfg, extra)
    _cli_print_size_report(root)
    print(f"📄 {len(files)} files")
    created = write_output(
        root, files, args.output, "all",
        not args.no_tree, args.chars, cfg.strip_explanations,
    )
    _cli_print_created(created)


def _cli_pick(args: argparse.Namespace, cfg: AppConfig) -> None:
    root = _resolve_target_path(args.path)
    if not root.is_dir():
        print(f"❌ Not a directory: {root}")
        return
    patterns: list[str] = getattr(args, "files", None) or []
    if not patterns or patterns == ["-"]:
        print("📝 Paths (one per line, empty = done):")
        patterns = []
        while True:
            try:
                line = input("  > ").strip()
            except EOFError:
                print()
                break
            if not line:
                break
            patterns.append(line)
    if not patterns:
        print("❌ No files specified")
        return
    extra = set(args.ignore) if args.ignore else None
    all_f = get_all_files(root, cfg, extra)
    _cli_print_size_report(root)
    picked, unmatched = resolve_patterns(root, patterns, all_f)
    for u in unmatched:
        print(f"  ⚠️  Not found: {u}")
    if not picked:
        print("❌ No matches")
        return
    print(f"📄 {len(picked)} files")
    created = write_output(
        root, picked, args.output, "pick",
        not args.no_tree, args.chars, cfg.strip_explanations,
    )
    _cli_print_created(created)


def _cli_tree(args: argparse.Namespace, cfg: AppConfig) -> None:
    root = _resolve_target_path(args.path)
    if not root.is_dir():
        print(f"❌ Not a directory: {root}")
        return
    if args.level is not None and args.level < 0:
        print("❌ --level must be >= 0")
        return
    extra = set(args.ignore) if args.ignore else None
    files = get_all_files(root, cfg, extra)
    _cli_print_size_report(root)
    tree = build_tree(
        root,
        files,
        sizes=getattr(args, "sizes", False),
        level=args.level,
        cfg=cfg,
        extra_ignore=extra,
    )
    print(f"\n{tree}")
    print(f"\n📄 Total: {len(files)}")


def _cli_find(args: argparse.Namespace, cfg: AppConfig) -> None:
    root = _resolve_target_path(args.path)
    if not root.is_dir():
        print(f"❌ Not a directory: {root}")
        return
    pat: str = args.pattern
    all_f = get_all_files(root, cfg)
    matched = [
        f for f in all_f
        if matches_pattern(
            str(f.relative_to(root)).replace("\\", "/"), f.name, pat,
        )
    ]
    if not matched:
        print(f"❌ Nothing matching: {pat}")
        return
    print(f"\n🔍 {len(matched)} files:\n")
    parts: list[str] = []
    for f in matched:
        rel = str(f.relative_to(root)).replace("\\", "/")
        print(f"  {rel}  ({fmt_size(f.stat().st_size)})")
        parts.append(f'"{rel}"')
    print(f'\n💡 sfc pick {" ".join(parts)}')


def _cli_from(args: argparse.Namespace, cfg: AppConfig) -> None:
    lf = Path(args.list_file)
    if not lf.exists():
        print(f"❌ Not found: {lf}")
        return
    patterns = [
        line.strip()
        for line in lf.read_text("utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    if not patterns:
        print("❌ Empty list")
        return
    args.files = patterns
    _cli_pick(args, cfg)


def _cli_preset(args: argparse.Namespace, cfg: AppConfig) -> None:
    root = _resolve_target_path(args.path)
    presets = load_presets(root)
    pa: list[str] = getattr(args, "preset_args", []) or []
    if not pa:
        print("Usage: preset list | save <name> files... | delete <name> | <name>")
        return
    action = pa[0]
    if action == "list":
        if not presets:
            print("📋 No presets")
            return
        for name, pats in sorted(presets.items()):
            print(f"  🔖 {name}: {', '.join(pats)}")
    elif action == "save":
        if len(pa) < 3:
            print("Usage: preset save <name> file1 file2 ...")
            return
        presets[pa[1]] = pa[2:]
        save_presets(presets, root)
        print(f"✅ Saved '{pa[1]}'")
    elif action == "delete":
        if len(pa) < 2:
            print("Usage: preset delete <name>")
            return
        if pa[1] in presets:
            del presets[pa[1]]
            save_presets(presets, root)
            print("✅ Deleted")
        else:
            print("❌ Not found")
    else:
        name = action
        if name not in presets:
            print(f"❌ Preset '{name}' not found")
            return
        args.files = presets[name]
        _cli_pick(args, cfg)


# ════════════════════════════════════════════════════════════════════
#  OS FILE MANAGER INTEGRATION
# ════════════════════════════════════════════════════════════════════

def _open_file_manager(directory: Path) -> None:
    """Open the platform file manager for *directory*."""
    target = str(directory.resolve())
    system = platform.system()
    try:
        if system == "Linux":
            subprocess.Popen(["xdg-open", target])
        elif system == "Darwin":
            subprocess.Popen(["open", target])
        elif system == "Windows":
            subprocess.Popen(["explorer", target])
        else:
            print(f"⚠️  Unsupported OS for auto-open: {system}")
    except FileNotFoundError:
        print("⚠️  File manager command not found")
    except OSError as exc:
        print(f"⚠️  Cannot open file manager: {exc}")


def _prompt_open_file_manager(directory: Path) -> None:
    """Ask the user whether to open the output directory."""
    try:
        answer = input("\n  📂 Open directory in file manager? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    if answer in ("y", "yes"):
        _open_file_manager(directory)


def _cli_print_created(created: list[tuple[Path, int]]) -> None:
    if not created:
        print("⚠️  No output")
        return
    print(f"\n  ✅ {len(created)} file(s):")
    for fn, ch in created:
        print(f"     📄 {fn.name}: {ch:,} chars")
    _prompt_open_file_manager(created[0][0].parent)


def _cli_print_size_report(root: Path) -> None:
    total, dependencies = project_size_report(root)
    print(f"Total project size: {fmt_size(total)}")
    for name, size, percent in dependencies:
        print(f"Dependency [{name}]: {fmt_size(size)} ({percent:.1f}%)")


# ════════════════════════════════════════════════════════════════════
#  CLI PARSER
# ════════════════════════════════════════════════════════════════════

def _build_parser(cfg: AppConfig) -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("-p", "--path", default=".")
    common.add_argument("-o", "--output", default=cfg.output)
    common.add_argument("-c", "--chars", type=int, default=cfg.max_chars)
    common.add_argument("--no-tree", action="store_true")
    common.add_argument("-i", "--ignore", nargs="*", default=[])
    common.add_argument(
        "--strip", action="store_true", default=cfg.strip_explanations,
        help="Strip comments/docstrings from .py files (AST)",
    )

    parser = argparse.ArgumentParser(
        prog="sfc",
        description=f"🔧 {APP_TITLE} v{VERSION}",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("-V", "--version", action="version", version=f"sfc {VERSION}")
    parser.add_argument(
        "--update",
        action="store_true",
        help="Download the latest sfc.pyz and replace the current executable",
    )
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("all", parents=[common])

    sp = sub.add_parser("pick", parents=[common])
    sp.add_argument("files", nargs="*")

    st = sub.add_parser("tree", parents=[common])
    st.add_argument("-s", "--sizes", action="store_true")
    st.add_argument("-l", "--level", type=int, default=None)

    sf = sub.add_parser("find", parents=[common])
    sf.add_argument("pattern")

    sfr = sub.add_parser("from", parents=[common])
    sfr.add_argument("list_file")

    spr = sub.add_parser("preset", parents=[common])
    spr.add_argument("preset_args", nargs="*")

    return parser


# ════════════════════════════════════════════════════════════════════
#  SENTINEL
# ════════════════════════════════════════════════════════════════════

class _ExitApp(Exception):
    """Raised to cleanly exit the main menu loop."""


# ════════════════════════════════════════════════════════════════════
#  INTERACTIVE TUI APPLICATION
# ════════════════════════════════════════════════════════════════════

class App:
    """Interactive TUI application state and screen routing."""

    def __init__(
        self,
        root: Path,
        cfg: AppConfig,
        extra_ignore: set[str] | None = None,
    ) -> None:
        self.root: Path = root.resolve()
        self.cfg: AppConfig = cfg
        self.extra_ignore: set[str] | None = extra_ignore
        self.selected: set[str] = set()
        self.all_files: list[Path] = []
        self.rel_paths: list[str] = []
        self._refresh_files()

        from sfc.tui import get_engine
        self.engine = get_engine()

    def _refresh_files(self) -> None:
        self.all_files = get_all_files(self.root, self.cfg, self.extra_ignore)
        self.rel_paths = [
            str(f.relative_to(self.root)).replace("\\", "/")
            for f in self.all_files
        ]
        self.selected = {s for s in self.selected if s in set(self.rel_paths)}

    def run(self) -> None:
        self.engine.start()
        try:
            self._main_menu()
        except KeyboardInterrupt:
            raise
        finally:
            self.engine.stop()

    # ── Main Menu ──────────────────────────────────────────────────

    def _update_menu_label(self) -> str:
        remote = get_background_update_version()
        if not remote:
            label = "🔄  Check for updates"
        else:
            shown = remote if remote.lower().startswith("v") else f"v{remote}"
            label = f"⭐  UPDATE AVAILABLE: {shown}"
        # Tag old versions as not recommended
        if _is_version_below_5(VERSION):
            label += "  \033[91m[Not Recommended]\033[0m"
        return label

    def _main_menu(self) -> None:
        from sfc.tui.base import MenuItem, Key, KeyEvent

        while True:
            sel_count = len(self.selected)

            title = [
                f"      🔧 {APP_TITLE} v{VERSION} ",
                f"  📂 Project: {self.root.name}  │  📄 Files: {len(self.all_files)}"
                + (f"  │  ✓ {sel_count} selected" if sel_count else ""),
            ]

            items = [
                MenuItem("📂  Browse & Select", "browse"),
                MenuItem("🔍  Search by pattern", "search"),
                MenuItem("📝  Quick pick (paste paths)", "quick_pick"),
                MenuItem("📋  Collect ALL files", "collect_all"),
                MenuItem("🔖  Presets", "presets"),
                MenuItem("🗂️   View tree", "tree"),
                MenuItem("🔧   Settings", "settings"),
                MenuItem("📖  Help", "help"),
                MenuItem(self._update_menu_label(), "update"),
                MenuItem("─" * 30, "_sep1", enabled=False),
                MenuItem(
                    f"✅  Collect selected ({sel_count})",
                    "collect",
                    enabled=sel_count > 0,
                ),
                MenuItem(
                    "🗑️   Clear selection",
                    "clear_sel",
                    enabled=sel_count > 0,
                ),
                MenuItem("─" * 30, "_sep2", enabled=False),
                MenuItem("❌  Exit", "exit"),
            ]

            footer = ["  ↑↓:navigate  ENTER:select  q:quit"]

            def on_select(item: MenuItem, idx: int) -> bool:
                return True

            def on_key(ev: KeyEvent, _items: list[MenuItem], cur: int) -> int | None:
                if ev.key is Key.CHAR and ev.char in ("q", "Q"):
                    raise _ExitApp
                return None

            def on_tick(menu_items: list[MenuItem]) -> bool:
                update_label = self._update_menu_label()
                for menu_item in menu_items:
                    if menu_item.value == "update":
                        menu_item.label = update_label
                        break
                return not is_background_update_check_done()

            try:
                chosen = self.engine.menu_loop(
                    title, items, footer, on_select,
                    on_key=on_key, on_tick=on_tick,
                )
            except _ExitApp:
                return

            if chosen is None:
                return

            action = chosen.value
            if action == "exit":
                return
            elif action == "browse":
                self._browse()
            elif action == "search":
                self._search()
            elif action == "quick_pick":
                self._quick_pick()
            elif action == "collect_all":
                self._collect_all()
            elif action == "presets":
                self._presets_menu()
            elif action == "tree":
                self._tree_view()
            elif action == "settings":
                self._settings_menu()
            elif action == "help":
                self._help_menu()
            elif action == "update":
                self._update_screen()
            elif action == "collect":
                self._do_collect()
            elif action == "clear_sel":
                self.selected.clear()
                self.engine.show_message("✓ Selection cleared")

    # ── Browse & Select ────────────────────────────────────────────

    def _browse(self) -> None:
        from sfc.tui.base import MenuItem, Key, KeyEvent

        filter_text: str = ""

        while True:
            if filter_text:
                ft = filter_text.lower()
                indices = [
                    i for i, r in enumerate(self.rel_paths)
                    if ft in r.lower()
                ]
            else:
                indices = list(range(len(self.rel_paths)))

            if not indices:
                self.engine.show_message(f"No files match: '{filter_text}'")
                filter_text = ""
                continue

            items: list[MenuItem] = []
            for gi in indices:
                rel = self.rel_paths[gi]
                fp = self.all_files[gi]
                try:
                    sz = fmt_size(fp.stat().st_size)
                except OSError:
                    sz = "?"
                items.append(
                    MenuItem(
                        label=rel,
                        value=rel,
                        checked=rel in self.selected,
                        suffix=sz,
                    )
                )

            finfo = f"  filter: '{filter_text}'" if filter_text else ""
            title = [
                f"  📂 Browse  ({len(indices)} files){finfo}",
                f"  ✓ {len(self.selected)} selected" if self.selected else "",
            ]
            footer_lines = [
                "  SPACE:toggle  ENTER:done  /:filter  a:all  n:none  p:glob  ESC:back",
            ]

            done: bool = False

            def on_check(item: MenuItem, idx: int) -> None:
                if item.checked:
                    self.selected.add(item.value)
                else:
                    self.selected.discard(item.value)

            def on_select(item: MenuItem, idx: int) -> bool:
                nonlocal done
                done = True
                return True

            def on_key(
                ev: KeyEvent, menu_items: list[MenuItem], cur: int,
            ) -> int | None:
                nonlocal filter_text, done

                if ev.key is Key.CHAR:
                    ch = ev.char.lower()
                    if ch == "/":
                        result = self.engine.prompt("Filter: ")
                        if result is not None:
                            filter_text = result
                        done = True
                        return -999
                    elif ch == "a":
                        for it in menu_items:
                            it.checked = True
                            self.selected.add(it.value)
                        return cur
                    elif ch == "n":
                        for it in menu_items:
                            it.checked = False
                            self.selected.discard(it.value)
                        return cur
                    elif ch == "p":
                        pat = self.engine.prompt("Glob pattern: ")
                        if pat:
                            count = 0
                            for it in menu_items:
                                if matches_pattern(
                                    it.value, Path(it.value).name, pat,
                                ):
                                    it.checked = True
                                    self.selected.add(it.value)
                                    count += 1
                            self.engine.show_message(
                                f"+{count} selected by '{pat}'"
                            )
                        return cur
                    elif ch == "c":
                        filter_text = ""
                        done = True
                        return -999
                return None

            result = self.engine.menu_loop(
                title, items, footer_lines, on_select, on_check, on_key,
            )

            # Sync checkbox state back
            for item in items:
                if item.checked:
                    self.selected.add(item.value)
                else:
                    self.selected.discard(item.value)

            if result is None and not done:
                return
            if done and not filter_text and result is not None:
                return

    # ── Search ─────────────────────────────────────────────────────

    def _search(self) -> None:
        from sfc.tui.base import MenuItem, Key, KeyEvent

        pat = self.engine.prompt("Search glob: ")
        if not pat:
            return

        matched_indices = [
            i for i, rel in enumerate(self.rel_paths)
            if matches_pattern(rel, Path(rel).name, pat)
        ]

        if not matched_indices:
            self.engine.show_message(f"❌ Nothing matches: {pat}")
            return

        items = [
            MenuItem(
                label=self.rel_paths[i],
                value=self.rel_paths[i],
                checked=self.rel_paths[i] in self.selected,
            )
            for i in matched_indices
        ]

        title = [f"  🔍 Results for '{pat}' — {len(items)} files"]
        footer = ["  SPACE:toggle  a:all  n:none  ENTER/ESC:back"]

        def on_check(item: MenuItem, idx: int) -> None:
            if item.checked:
                self.selected.add(item.value)
            else:
                self.selected.discard(item.value)

        def on_key(
            ev: KeyEvent, menu_items: list[MenuItem], cur: int,
        ) -> int | None:
            if ev.key is Key.CHAR:
                if ev.char.lower() == "a":
                    for it in menu_items:
                        it.checked = True
                        self.selected.add(it.value)
                    return cur
                if ev.char.lower() == "n":
                    for it in menu_items:
                        it.checked = False
                        self.selected.discard(it.value)
                    return cur
            return None

        self.engine.menu_loop(
            title, items, footer, on_check=on_check, on_key=on_key,
        )

        for item in items:
            if item.checked:
                self.selected.add(item.value)
            else:
                self.selected.discard(item.value)

    # ── Quick Pick ─────────────────────────────────────────────────

    def _quick_pick(self) -> None:
        self.engine.show_message(
            "📝 Quick Pick\n\n"
            "Enter paths/patterns one per line.\n"
            "Press ENTER on empty line to finish.",
            wait=False,
        )
        patterns: list[str] = []
        while True:
            line = self.engine.prompt("path> ")
            if line is None:
                return
            if line == "":
                break
            patterns.append(line)

        if not patterns:
            return

        picked, unmatched = resolve_patterns(
            self.root, patterns, self.all_files,
        )
        for fp in picked:
            self.selected.add(
                str(fp.relative_to(self.root)).replace("\\", "/")
            )

        msg = f"✓ {len(picked)} files added"
        if unmatched:
            msg += f"\n⚠️ Not found: {', '.join(unmatched)}"
        self.engine.show_message(msg)

    # ── Collect All ────────────────────────────────────────────────

    def _collect_all(self) -> None:
        if not self.all_files:
            self.engine.show_message("⚠️ No files found")
            return
        created = write_output(
            self.root, self.all_files, self.cfg.output,
            "all", self.cfg.show_tree, self.cfg.max_chars,
            self.cfg.strip_explanations,
        )
        self._offer_clipboard(created)

    # ── Collect Selected (with dynamic uncheck) ────────────────────

    def _do_collect(self) -> None:
        from sfc.tui.base import MenuItem

        if not self.selected:
            self.engine.show_message("⚠️ Nothing selected")
            return

        sorted_sel = sorted(self.selected)
        items = [
            MenuItem(label=rel, value=rel, checked=True)
            for rel in sorted_sel
        ]

        title = [
            f"  ✅ Collect — {len(items)} files",
            "  Uncheck items to exclude before collecting",
        ]
        footer = ["  SPACE:toggle  ENTER:collect  ESC:cancel"]

        result = self.engine.menu_loop(
            title, items, footer,
            on_select=lambda item, idx: True,
        )

        if result is None:
            return

        final_rels = [item.value for item in items if item.checked]
        if not final_rels:
            self.engine.show_message(
                "⚠️ All items unchecked — nothing to collect"
            )
            return

        files = [
            self.root / r for r in final_rels
            if (self.root / r).exists()
        ]
        if not files:
            self.engine.show_message("❌ No valid files")
            return

        created = write_output(
            self.root, files, self.cfg.output,
            "pick", self.cfg.show_tree, self.cfg.max_chars,
            self.cfg.strip_explanations,
        )
        self._offer_clipboard(created)

    # ── Tree ───────────────────────────────────────────────────────

    def _tree_view(self) -> None:
        tree_text = build_tree(self.root, self.all_files, sizes=True)
        colored_lines = []
        for line in tree_text.splitlines():
            if "📂" in line or "📦" in line:
                colored_lines.append(f"\033[36m{line}\033[0m")
            elif "📄" in line:
                colored_lines.append(f"\033[32m{line}\033[0m")
            else:
                colored_lines.append(line)
        colored_text = "\n".join(colored_lines)
        colored_text += f"\n\n 📄 Total: {len(self.all_files)} files"
        self.engine.draw_text_block(colored_text)

    # ── Settings ───────────────────────────────────────────────────

    def _settings_menu(self) -> None:
        from sfc.tui.base import MenuItem

        while True:
            tree_s = "ON" if self.cfg.show_tree else "OFF"
            copy_s = "ON" if self.cfg.auto_copy else "OFF"
            strip_s = "ON" if self.cfg.strip_explanations else "OFF"
            ads_s = "ON" if self.cfg.show_ads else "OFF"
            clip_backend = available_backend() or "none"

            items = [
                MenuItem(
                    f"Output file:        {self.cfg.output}", "output",
                ),
                MenuItem(
                    f"Max chars/part:     {self.cfg.max_chars:,}", "max_chars",
                ),
                MenuItem(
                    f"Include tree:       {tree_s}", "toggle_tree",
                ),
                MenuItem(
                    f"Auto clipboard:     {copy_s}", "toggle_copy",
                ),
                MenuItem(
                    f"Page size:          {self.cfg.page_size}", "page_size",
                ),
                MenuItem(
                    f"Comment Killer:     {strip_s}", "toggle_strip",
                ),
                MenuItem(
                    f"Show SFC PRO ads:   {ads_s}", "toggle_ads",
                ),
                MenuItem(
                    f"Clipboard backend:  {clip_backend}",
                    "_clip", enabled=False,
                ),
                MenuItem("─" * 30, "_sep_presets", enabled=False),
                MenuItem("💾  Save config preset", "save_cfg_preset"),
                MenuItem("📂  Load config preset", "load_cfg_preset"),
                MenuItem("─" * 30, "_sep", enabled=False),
                MenuItem("🚫  Ignoring (dirs/files/ext)", "ignoring"),
                MenuItem(
                    f"🔄  Refresh files  ({len(self.all_files)} indexed)",
                    "refresh",
                ),
                MenuItem("─" * 30, "_sep2", enabled=False),
                MenuItem("↩   Back", "back"),
            ]

            title = ["  🔧 Settings"]
            result = self.engine.menu_loop(
                title, items, on_select=lambda item, idx: True,
            )

            if result is None or result.value == "back":
                save_config(self.cfg)
                return

            v = result.value
            if v == "output":
                val = self.engine.prompt("Output file: ", self.cfg.output)
                if val:
                    self.cfg.output = val
            elif v == "max_chars":
                val = self.engine.prompt(
                    "Max chars: ", str(self.cfg.max_chars),
                )
                if val:
                    try:
                        self.cfg.max_chars = max(1000, int(val))
                    except ValueError:
                        pass
            elif v == "toggle_tree":
                self.cfg.show_tree = not self.cfg.show_tree
            elif v == "toggle_copy":
                self.cfg.auto_copy = not self.cfg.auto_copy
            elif v == "toggle_strip":
                self.cfg.strip_explanations = not self.cfg.strip_explanations
                state = "ON" if self.cfg.strip_explanations else "OFF"
                self.engine.show_message(
                    f"🔧 Comment Killer: {state}\n\n"
                    "When ON, docstrings and # comments\n"
                    "are stripped from .py files during collect."
                )
            elif v == "page_size":
                val = self.engine.prompt(
                    "Page size: ", str(self.cfg.page_size),
                )
                if val:
                    try:
                        self.cfg.page_size = max(5, min(100, int(val)))
                    except ValueError:
                        pass
            elif v == "toggle_ads":
                self.cfg.show_ads = not self.cfg.show_ads
                state = "ON" if self.cfg.show_ads else "OFF"
                self.engine.show_message(f"📢 SFC PRO ads: {state}")
            elif v == "ignoring":
                self._ignoring_menu()
            elif v == "refresh":
                self._refresh_files()
                self.engine.show_message(
                    f"✓ {len(self.all_files)} files indexed"
                )
            elif v == "save_cfg_preset":
                name = self.engine.prompt("Preset name: ")
                if name:
                    from sfc.config import save_config_preset
                    save_config_preset(name, self.cfg)
                    self.engine.show_message(f"✓ Saved config preset '{name}'")
            elif v == "load_cfg_preset":
                from sfc.config import list_config_presets, load_config_preset
                presets = list_config_presets()
                if not presets:
                    self.engine.show_message("No config presets found")
                    continue
                from sfc.tui.base import MenuItem as MI
                p_items = [MI(p, p) for p in presets]
                p_items.append(MI("↩   Back", "back"))
                res = self.engine.menu_loop(
                    ["  Load Config Preset"], p_items,
                    on_select=lambda i, idx: True,
                )
                if res and res.value != "back":
                    loaded = load_config_preset(res.value)
                    if loaded:
                        self.cfg = loaded
                        save_config(self.cfg)
                        self._refresh_files()
                        self.engine.show_message(f"✓ Loaded config preset '{res.value}'")

    # ── Ignoring Sub-Menu ──────────────────────────────────────────

    def _ignoring_menu(self) -> None:
        from sfc.tui.base import MenuItem

        while True:
            items = [
                MenuItem(
                    f"Ignored directories  ({len(self.cfg.ignore_dirs)})",
                    "dirs",
                ),
                MenuItem(
                    f"Ignored files        ({len(self.cfg.ignore_files)})",
                    "files",
                ),
                MenuItem(
                    f"Ignored extensions   ({len(self.cfg.ignore_extensions)})",
                    "exts",
                ),
                MenuItem("─" * 30, "_sep", enabled=False),
                MenuItem("🔄  Reset ALL to defaults", "reset"),
                MenuItem("📖  Filter help", "help"),
                MenuItem("↩   Back", "back"),
            ]

            title = ["  🚫 Ignoring Settings"]
            result = self.engine.menu_loop(
                title, items, on_select=lambda i, idx: True,
            )

            if result is None or result.value == "back":
                save_config(self.cfg)
                self._refresh_files()
                return

            v = result.value
            if v == "dirs":
                self._edit_ignore_list(
                    "Ignored Directories", self.cfg.ignore_dirs,
                )
            elif v == "files":
                self._edit_ignore_list(
                    "Ignored Files", self.cfg.ignore_files,
                )
            elif v == "exts":
                self._edit_ignore_list(
                    "Ignored Extensions", self.cfg.ignore_extensions,
                )
            elif v == "reset":
                if self.engine.confirm(
                    "Reset all ignore lists to defaults?"
                ):
                    self.cfg.reset_ignores()
                    save_config(self.cfg)
                    self._refresh_files()
                    self.engine.show_message("✓ Reset to defaults")
            elif v == "help":
                self.engine.draw_text_block(HELP_FILTERS)

    def _edit_ignore_list(self, title: str, lst: list[str]) -> None:
        from sfc.tui.base import MenuItem, Key, KeyEvent

        while True:
            items = [
                MenuItem(entry, entry, checked=True)
                for entry in sorted(lst)
            ]
            items.append(MenuItem("─" * 30, "_sep", enabled=False))
            items.append(MenuItem("➕  Add new entry", "add"))
            items.append(MenuItem("↩   Back", "back"))

            header = [
                f"  {title} ({len(lst)} entries)",
                "  Uncheck to remove",
            ]
            footer = [
                "  SPACE:remove  ENTER:action  a:add  ESC:back",
            ]

            removed: set[str] = set()

            def on_check(item: MenuItem, idx: int) -> None:
                if not item.checked:
                    removed.add(item.value)
                else:
                    removed.discard(item.value)

            def on_key(
                ev: KeyEvent,
                menu_items: list[MenuItem],
                cur: int,
            ) -> int | None:
                if ev.key is Key.CHAR and ev.char.lower() == "a":
                    val = self.engine.prompt("Add: ")
                    if val and val.strip():
                        entry = val.strip()
                        if entry not in lst:
                            lst.append(entry)
                    return -999
                return None

            result = self.engine.menu_loop(
                header, items, footer,
                on_select=lambda item, idx: True,
                on_check=on_check,
                on_key=on_key,
            )

            if removed:
                for entry in removed:
                    if entry in lst:
                        lst.remove(entry)

            if result is None or (
                result is not None and result.value == "back"
            ):
                return

            if result is not None and result.value == "add":
                val = self.engine.prompt("Add: ")
                if val and val.strip():
                    entry = val.strip()
                    if entry not in lst:
                        lst.append(entry)

    # ── Presets ────────────────────────────────────────────────────

    def _presets_menu(self) -> None:
        from sfc.tui.base import MenuItem

        while True:
            presets = load_presets(self.root)
            names = sorted(presets.keys())

            items: list[MenuItem] = []
            for name in names:
                pats = presets[name]
                items.append(MenuItem(
                    f"🔖 {name}  ({len(pats)} patterns)",
                    f"use:{name}",
                ))

            if not items:
                items.append(MenuItem(
                    "  (no presets yet)", "_empty", enabled=False,
                ))

            items.append(MenuItem("─" * 30, "_sep", enabled=False))
            items.append(MenuItem("🔖 [Built-in] Structure only", "use_builtin:structure_only"))
            items.append(MenuItem("─" * 30, "_sep2", enabled=False))
            items.append(MenuItem("💾  Save selection as preset", "save"))
            items.append(MenuItem("🗑️   Delete a preset", "delete"))
            items.append(MenuItem("📤  Export preset → collect", "export"))
            items.append(MenuItem("↩   Back", "back"))

            title = ["  🔖 Presets"]
            result = self.engine.menu_loop(
                title, items, on_select=lambda item, idx: True,
            )

            if result is None or result.value == "back":
                return

            v = result.value
            if v == "use_builtin:structure_only":
                created = write_output(
                    self.root,
                    self.all_files,
                    self.cfg.output,
                    mode="preset:Structure only",
                    show_tree=True,
                    max_chars=self.cfg.max_chars,
                    strip_explanations=self.cfg.strip_explanations,
                    structure_only=True,
                )
                self._offer_clipboard(created)

            elif v.startswith("use:"):
                name = v[4:]
                picked, _ = resolve_patterns(
                    self.root, presets[name], self.all_files,
                )
                for fp in picked:
                    self.selected.add(
                        str(fp.relative_to(self.root)).replace("\\", "/")
                    )
                self.engine.show_message(
                    f"✓ +{len(picked)} files from '{name}'"
                )

            elif v == "save":
                if not self.selected:
                    self.engine.show_message("⚠️ Nothing selected")
                    continue
                name = self.engine.prompt("Preset name: ")
                if name:
                    presets[name] = sorted(self.selected)
                    save_presets(presets, self.root)
                    self.engine.show_message(
                        f"✓ Saved '{name}' ({len(self.selected)} files)"
                    )

            elif v == "delete":
                if not names:
                    self.engine.show_message("No presets to delete")
                    continue
                del_items = [MenuItem(n, n) for n in names]
                del_result = self.engine.menu_loop(
                    ["  Delete preset"], del_items,
                    on_select=lambda item, idx: True,
                )
                if del_result and del_result.value in presets:
                    if self.engine.confirm(
                        f"Delete '{del_result.value}'?"
                    ):
                        del presets[del_result.value]
                        save_presets(presets, self.root)
                        self.engine.show_message("✓ Deleted")

            elif v == "export":
                if not names:
                    self.engine.show_message("No presets to export")
                    continue
                exp_items = [MenuItem(n, n) for n in names]
                exp_result = self.engine.menu_loop(
                    ["  Export preset"], exp_items,
                    on_select=lambda item, idx: True,
                )
                if exp_result and exp_result.value in presets:
                    picked, _ = resolve_patterns(
                        self.root,
                        presets[exp_result.value],
                        self.all_files,
                    )
                    if picked:
                        created = write_output(
                            self.root, picked, self.cfg.output,
                            f"preset:{exp_result.value}",
                            self.cfg.show_tree, self.cfg.max_chars,
                            self.cfg.strip_explanations,
                        )
                        self._offer_clipboard(created)

    # ── Help ───────────────────────────────────────────────────────

    def _help_menu(self) -> None:
        from sfc.tui.base import MenuItem

        items = [
            MenuItem("📖  Glob Patterns", "glob"),
            MenuItem("📖  Presets Guide", "presets"),
            MenuItem("📖  Filters & Ignoring", "filters"),
            MenuItem("↩   Back", "back"),
        ]
        while True:
            result = self.engine.menu_loop(
                ["  📖 Help"], items,
                on_select=lambda i, idx: True,
            )
            if result is None or result.value == "back":
                return
            if result.value == "glob":
                self.engine.draw_text_block(HELP_GLOB)
            elif result.value == "presets":
                self.engine.draw_text_block(HELP_PRESETS)
            elif result.value == "filters":
                self.engine.draw_text_block(HELP_FILTERS)

    # ── Update ─────────────────────────────────────────────────────

    def _update_screen(self) -> None:
        self.engine.show_message("🔄 Checking for updates...", wait=False)
        result = check_update()

        if result.error:
            self.engine.show_message(f"❌ {result.error}")
            return

        if not result.available:
            msg = f"✅ You are on the latest version ({result.current_version})"
            if _is_version_below_5(result.current_version):
                msg += (
                    "\n\n\033[91m⚠️  [Not Recommended] Versions below 5.0.0 are outdated."
                    "\nPlease upgrade to v5.0.0 for full support.\033[0m"
                )
            self.engine.show_message(msg)
            return

        if not self.engine.confirm(
            f"Update: {result.current_version} → {result.remote_version}. Install?"
        ):
            return

        self.engine.show_message("⬇️  Downloading update...", wait=False)
        apply_result = apply_update()

        if apply_result.ok:
            self.engine.show_message(f"✅ {apply_result.message}")
            # If the updater says to exit (Windows .exe batch workaround),
            # we must actually terminate so the batch script can replace us.
            if "close now" in apply_result.message.lower():
                self.engine.show_message(
                    "🔄 sfc will exit now for the update to complete.\n"
                    "Please restart after a few seconds.",
                )
                self.engine.stop()
                sys.exit(0)
        else:
            self.engine.show_message(f"❌ {apply_result.message}")

    # ── Clipboard ──────────────────────────────────────────────────

    def _offer_clipboard(self, created: list[tuple[Path, int]]) -> None:
        if not created:
            self.engine.show_message("⚠️ No output files created")
            return

        msg_lines: list[str] = [f"✅ {len(created)} file(s) written:"]
        for fn, ch in created:
            msg_lines.append(f"  📄 {fn.name}: {ch:,} chars")

        if self.cfg.auto_copy:
            self._do_copy(created, msg_lines)
        else:
            msg_lines.append("")
            self.engine.show_message("\n".join(msg_lines), wait=False)

            if self.engine.confirm("Copy to clipboard?"):
                self._do_copy(created, [])
            else:
                self.engine.show_message("\n".join(msg_lines))

        # Offer to open the output directory in the platform file manager
        if created and self.engine.confirm("📂 Open directory in file manager?"):
            _open_file_manager(created[0][0].parent)

    def _do_copy(
        self,
        created: list[tuple[Path, int]],
        extra_msg: list[str],
    ) -> None:
        try:
            text = "".join(
                Path(fn).read_text("utf-8") for fn, _ in created
            )
            result: ClipboardResult = copy_to_clipboard(text)
            if result.ok:
                extra_msg.append(f"📋 Copied via {result.backend}")
            else:
                extra_msg.append(f"⚠️ Clipboard: {result.error}")
        except Exception as exc:
            extra_msg.append(f"⚠️ {exc}")

        self.engine.show_message(
            "\n".join(extra_msg) if extra_msg else "Done"
        )


# ════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ════════════════════════════════════════════════════════════════════

def run(argv: list[str] | None = None) -> None:
    """Main entry point with user-friendly interruption/errors."""
    try:
        _run(argv)
    except KeyboardInterrupt:
        _exit_stopped_by_user()
    except MaxFilesLimitError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(1)


def _run(argv: list[str] | None = None) -> None:
    """Dispatch to CLI or interactive TUI."""
    if argv is None:
        argv = sys.argv[1:]

    cfg: AppConfig = load_config()

    _show_ad_banner(cfg)

    # No args → interactive
    if not argv:
        root = _resolve_target_path(".")
        _start_background_update_check()
        App(root, cfg).run()
        return

    parser = _build_parser(cfg)
    args = parser.parse_args(argv)

    if args.update:
        result = update_current_binary()
        if result.ok:
            print(f"✅ {result.message}")
        else:
            print(f"❌ {result.message}")
        return

    # Apply --strip flag to cfg
    if hasattr(args, "strip") and args.strip:
        cfg.strip_explanations = True

    if not args.cmd:
        root = _resolve_target_path(args.path)
        extra = set(args.ignore) if args.ignore else None
        cfg.output = args.output
        cfg.max_chars = args.chars
        _start_background_update_check()
        App(root, cfg, extra).run()
        return

    handlers = {
        "all": _cli_all,
        "pick": _cli_pick,
        "tree": _cli_tree,
        "find": _cli_find,
        "from": _cli_from,
        "preset": _cli_preset,
    }
    handlers[args.cmd](args, cfg)
