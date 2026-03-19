# ── sfc build system ────────────────────────────────────────────
# Targets:
#   make zipapp   → dist/sfc.pyz   (any OS, any Python — ALWAYS works)
#   make win      → dist/sfc.exe   (run ON Windows with shared Python)
#   make linux    → dist/sfc       (run ON Linux with shared Python)
#   make macos    → dist/sfc       (run ON macOS with shared Python)
#   make check    → verify PyInstaller prerequisites
#   make clean    → remove all build artifacts
#
# NOTE: PyInstaller targets require Python built with --enable-shared.
#       GitHub Codespaces Python does NOT have this. Use the zipapp
#       target instead, or run PyInstaller in CI / local machine.
# ────────────────────────────────────────────────────────────────
.PHONY: zipapp win linux macos clean all help check _check_pi

PYTHON   ?= python3
PKG      := sfc
DIST     := dist
STAGING  := _build_staging
APP      := sfc

help:
	@echo ""
	@echo "  sfc build targets"
	@echo "  ─────────────────────────────────────────────────────"
	@echo "  make zipapp   .pyz portable archive (works everywhere)"
	@echo "  make win      Windows .exe   (PyInstaller, native only)"
	@echo "  make linux    Linux binary   (PyInstaller, native only)"
	@echo "  make macos    macOS binary   (PyInstaller, native only)"
	@echo "  make check    verify PyInstaller prerequisites"
	@echo "  make clean    remove build artifacts"
	@echo ""

# ─── Check PyInstaller prerequisites ───────────────────────────
check:
	@$(PYTHON) build.py check

# ─── Clean ──────────────────────────────────────────────────────
clean:
	rm -rf $(DIST) $(STAGING) build *.spec
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "🧹 Clean"

# ─── Zipapp (.pyz) — zero dependencies, works everywhere ───────
zipapp:
	@rm -rf $(STAGING)
	@mkdir -p $(DIST) $(STAGING)
	cp -r $(PKG) $(STAGING)/$(PKG)
	find $(STAGING) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(STAGING) -name "*.pyc" -delete 2>/dev/null || true
	printf 'import sys\nfrom sfc.app import run\nrun(sys.argv[1:])\n' \
		> $(STAGING)/__main__.py
	$(PYTHON) -m zipapp $(STAGING) \
		--python "/usr/bin/env python3" \
		--output $(DIST)/$(APP).pyz \
		--compress
	rm -rf $(STAGING)
	chmod +x $(DIST)/$(APP).pyz 2>/dev/null || true
	@SIZE=$$(du -h $(DIST)/$(APP).pyz | cut -f1); \
	 echo "✅ Built: $(DIST)/$(APP).pyz  ($$SIZE)"

# ─── PyInstaller shared flags ──────────────────────────────────
_PI_COMMON = --onefile --clean --noconfirm \
	--name $(APP) \
	--distpath $(DIST) \
	--specpath $(DIST) \
	--paths . \
	--hidden-import $(PKG) \
	--hidden-import $(PKG).app \
	--hidden-import $(PKG).collector \
	--hidden-import $(PKG).config \
	--hidden-import $(PKG).clipboard \
	--hidden-import $(PKG).patterns \
	--hidden-import $(PKG).updater \
	--hidden-import $(PKG).version \
	--hidden-import $(PKG).tui \
	--hidden-import $(PKG).tui.base \
	--hidden-import $(PKG).tui.win_tui \
	--hidden-import $(PKG).tui.curses_tui \
	--exclude-module tkinter \
	--exclude-module unittest

# Preflight via build.py check (exits non-zero on failure)
_check_pi:
	@$(PYTHON) build.py check

# ─── Windows .exe ──────────────────────────────────────────────
win: _check_pi
	@mkdir -p $(DIST)
	$(PYTHON) -m PyInstaller $(_PI_COMMON) \
		--console \
		$(PKG)/__main__.py
	@echo "✅ Built: $(DIST)/$(APP).exe"

# ─── Linux ELF ─────────────────────────────────────────────────
linux: _check_pi
	@mkdir -p $(DIST)
	$(PYTHON) -m PyInstaller $(_PI_COMMON) \
		$(PKG)/__main__.py
	@echo "✅ Built: $(DIST)/$(APP)"

# ─── macOS ─────────────────────────────────────────────────────
macos: _check_pi
	@mkdir -p $(DIST)
	$(PYTHON) -m PyInstaller $(_PI_COMMON) \
		$(PKG)/__main__.py
	@echo "✅ Built: $(DIST)/$(APP)"

all: zipapp