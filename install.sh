#!/bin/sh
set -eu

INSTALL_DIR="$HOME/.local/bin"
API_URL="https://api.github.com/repos/Heysh1n/sfc/releases/latest"
USER_AGENT="sfc-installer"

# ── Colors ─────────────────────────────────────────────
if [ -t 1 ]; then
    BOLD="$(printf '\033[1m')"
    DIM="$(printf '\033[2m')"

    WHITE="$(printf '\033[37m')"
    BRIGHT_WHITE="$(printf '\033[97m')"

    MAGENTA="$(printf '\033[35m')"
    BRIGHT_MAGENTA="$(printf '\033[95m')"
    DIM_MAGENTA="$(printf '\033[2;35m')"

    RED="$(printf '\033[31m')"
    GREEN="$(printf '\033[32m')"
    YELLOW="$(printf '\033[33m')"
    CYAN="$(printf '\033[36m')"

    RESET="$(printf '\033[0m')"
else
    BOLD=""
    DIM=""
    WHITE=""
    BRIGHT_WHITE=""
    MAGENTA=""
    BRIGHT_MAGENTA=""
    DIM_MAGENTA=""
    RED=""
    GREEN=""
    YELLOW=""
    CYAN=""
    RESET=""
fi

# ── UI helpers ─────────────────────────────────────────
line() {
    printf "%s%s%s\n" "$DIM_MAGENTA" "──────────────────────────────────────────────" "$RESET"
}

info() {
    printf "%s→%s %s\n" "$MAGENTA" "$RESET" "$1"
}

success() {
    printf "%s✓%s %s\n" "$GREEN" "$RESET" "$1"
}

warn() {
    printf "%s⚠%s %s\n" "$YELLOW" "$RESET" "$1"
}

error() {
    printf "%s✗%s %s\n" "$RED" "$RESET" "$1"
}

logo() {
    printf "%s  ████████╗ ███████╗ ██████╗%s\n" "$BRIGHT_WHITE" "$RESET"
    printf "%s  ██╔════╝ ██╔════╝██╔════╝%s\n" "$WHITE" "$RESET"
    printf "%s  ███████╗ █████╗  ██║     %s\n" "$MAGENTA" "$RESET"
    printf "%s  ╚════██║ ██╔══╝  ██║     %s\n" "$BRIGHT_MAGENTA" "$RESET"
    printf "%s  ███████║ ██║     ╚██████╗%s\n" "$MAGENTA" "$RESET"
    printf "%s  ╚══════╝ ╚═╝      ╚═════╝%s\n" "$DIM_MAGENTA" "$RESET"
}

header() {
    clear 2>/dev/null || true
    printf "\n"
    printf "%s╭────────────────────────────────────────────╮%s\n" "$MAGENTA" "$RESET"
    printf "%s│%s              %sSFC Installer%s       %s  │%s\n" "$MAGENTA" "$RESET" "$BOLD" "$RESET" "$MAGENTA" "$RESET"
    printf "%s╰────────────────────────────────────────────╯%s\n" "$MAGENTA" "$RESET"
    printf "\n"
    logo
    printf "\n"
    printf "%sSmart File Collector%s\n" "$DIM" "$RESET"
    printf "\n"
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Required command not found: $1"
        exit 1
    fi
}

pause() {
    printf "\n%sPress Enter to continue...%s" "$DIM" "$RESET"
    read -r _ || true
}

# ── Release fetch ──────────────────────────────────────
fetch_release_info() {
    TMP_JSON="$(mktemp)"

    cleanup() {
        rm -f "$TMP_JSON"
    }

    trap cleanup EXIT INT TERM

    info "Fetching latest release data..."

    if ! curl -fsSL -H "User-Agent: $USER_AGENT" "$API_URL" -o "$TMP_JSON"; then
        error "Failed to fetch latest release data"
        exit 1
    fi

    RELEASE_INFO="$(python3 - "$TMP_JSON" <<'PY'
import json
import sys

path = sys.argv[1]

try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tag = data.get("tag_name")

    if not tag:
        print("ERROR|latest release tag_name not found")
        sys.exit(1)

    expected_name = f"sfc.{tag}.pyz"
    assets = data.get("assets", [])

    for asset in assets:
        name = asset.get("name")
        url = asset.get("browser_download_url")

        if name == expected_name and url:
            print(f"OK|{tag}|{expected_name}|{url}")
            sys.exit(0)

    asset_names = ", ".join(
        asset.get("name", "unknown")
        for asset in assets
    )

    if not asset_names:
        asset_names = "no assets"

    print(f"ERROR|{expected_name} asset not found in latest release. Found: {asset_names}")
    sys.exit(1)

except Exception as e:
    print(f"ERROR|Failed to parse GitHub API response ({e})")
    sys.exit(1)
PY
)"

    STATUS="$(printf "%s" "$RELEASE_INFO" | cut -d'|' -f1)"

    if [ "$STATUS" != "OK" ]; then
        MSG="$(printf "%s" "$RELEASE_INFO" | cut -d'|' -f2-)"
        error "$MSG"
        exit 1
    fi

    TAG="$(printf "%s" "$RELEASE_INFO" | cut -d'|' -f2)"
    ASSET_NAME="$(printf "%s" "$RELEASE_INFO" | cut -d'|' -f3)"
    DOWNLOAD_URL="$(printf "%s" "$RELEASE_INFO" | cut -d'|' -f4-)"

    success "Latest release: $TAG"
    success "Asset found: $ASSET_NAME"
}

# ── Install ────────────────────────────────────────────
install_sfc() {
    require_cmd curl
    require_cmd python3

    header
    printf "%sInstalling / Updating SFC%s\n\n" "$BOLD" "$RESET"

    fetch_release_info

    printf "\n"
    info "Install path: $INSTALL_DIR/sfc"

    mkdir -p "$INSTALL_DIR"

    info "Downloading package..."

    if ! curl -fsSL -H "User-Agent: $USER_AGENT" "$DOWNLOAD_URL" -o "$INSTALL_DIR/sfc"; then
        error "Failed to download SFC"
        exit 1
    fi

    chmod +x "$INSTALL_DIR/sfc"

    printf "\n"
    line
    success "SFC installed successfully"
    line
    printf "\n"

    if command -v sfc >/dev/null 2>&1; then
        printf "%sRun:%s\n" "$BOLD" "$RESET"
        printf "  %ssfc%s\n" "$BRIGHT_MAGENTA" "$RESET"
    else
        warn "$INSTALL_DIR is not in your PATH"
        printf "\n"

        printf "%sAdd it to PATH:%s\n" "$BOLD" "$RESET"
        printf "  export PATH=\"\$HOME/.local/bin:\$PATH\"\n"
        printf "\n"

        printf "%sFor macOS zsh:%s\n" "$BOLD" "$RESET"
        printf "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.zshrc\n"
        printf "  source ~/.zshrc\n"
        printf "\n"

        printf "%sFor Linux bash:%s\n" "$BOLD" "$RESET"
        printf "  echo 'export PATH=\"\$HOME/.local/bin:\$PATH\"' >> ~/.bashrc\n"
        printf "  source ~/.bashrc\n"
    fi
}

show_location() {
    header
    printf "%sInstall location%s\n\n" "$BOLD" "$RESET"
    info "$INSTALL_DIR/sfc"

    if [ -f "$INSTALL_DIR/sfc" ]; then
        success "SFC is installed"
    else
        warn "SFC is not installed yet"
    fi

    pause
}

show_menu() {
    while :; do
        header

        printf "%sSelect action:%s\n\n" "$BOLD" "$RESET"

        printf "  %s1%s) %sInstall / Update SFC locally%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s2%s) %sShow install location%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s3%s) %sExit%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"

        printf "\n"
        printf "%sChoice:%s " "$BOLD" "$RESET"

        read -r ACTION

        case "$ACTION" in
            1)
                install_sfc
                printf "\n"
                exit 0
                ;;
            2)
                show_location
                ;;
            3|0|q|Q)
                printf "\n"
                info "Exit."
                exit 0
                ;;
            *)
                printf "\n"
                error "Invalid option"
                pause
                ;;
        esac
    done
}

show_menu
