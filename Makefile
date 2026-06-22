.PHONY: build local-install uninstall zipapp clean help

PYTHON ?= python3
INSTALL_DIR := $(HOME)/.local/bin
INSTALL_PATH := $(INSTALL_DIR)/sfc

help:
	@echo "sfc unified build targets"
	@echo "  make build         Clean, sync version, and build ./dist/sfc.pyz"
	@echo "  make local-install Install to ~/.local/bin/sfc"
	@echo "  make uninstall     Remove ~/.local/bin/sfc"
	@echo "  make clean         Remove build artifacts"

clean:
	@$(PYTHON) build.py clean

build: clean
	@$(PYTHON) build.py build

local-install: build
	@mkdir -p $(INSTALL_DIR)
	@cp dist/sfc.pyz $(INSTALL_PATH)
	@chmod +x $(INSTALL_PATH)
	@echo "✅ Installed to $(INSTALL_PATH)"

uninstall:
	@if [ -f "$(INSTALL_PATH)" ]; then \
		rm -f "$(INSTALL_PATH)"; \
		echo "🗑️  Removed $(INSTALL_PATH)"; \
	else \
		echo "SFC is not installed at $(INSTALL_PATH)"; \
	fi