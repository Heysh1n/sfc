.PHONY: build local-install zipapp clean help

PYTHON ?= python3
PKG := sfc
APP := sfc
PYZ := sfc.pyz
DIST := dist
ZIPROOT := .zipapp_root

help:
	@echo "sfc build targets"
	@echo "  make build         Build ./sfc.pyz with stdlib zipapp"
	@echo "  make local-install Install ./sfc.pyz to ~/.local/bin/sfc"
	@echo "  make zipapp        Build ./dist/sfc.pyz"
	@echo "  make clean         Remove build artifacts"

build:
	@rm -rf $(ZIPROOT)
	@mkdir -p $(ZIPROOT)
	cp -R $(PKG) $(ZIPROOT)/$(PKG)
	find $(ZIPROOT) -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find $(ZIPROOT) -name "*.pyc" -delete 2>/dev/null || true
	$(PYTHON) -m zipapp $(ZIPROOT) -m "$(PKG).__main__:main" -o $(PYZ) -p "/usr/bin/env python3"
	@rm -rf $(ZIPROOT)
	chmod +x $(PYZ)
	@echo "Built $(PYZ)"

local-install: build
	mkdir -p $(HOME)/.local/bin
	cp $(PYZ) $(HOME)/.local/bin/$(APP)
	chmod +x $(HOME)/.local/bin/$(APP)
	@echo "Installed $(HOME)/.local/bin/$(APP)"

zipapp:
	@mkdir -p $(DIST)
	$(MAKE) build
	cp $(PYZ) $(DIST)/$(APP).pyz
	@echo "Built $(DIST)/$(APP).pyz"

clean:
	rm -rf $(DIST) $(ZIPROOT) build *.spec $(PYZ)
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleaned build artifacts"
