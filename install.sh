#!/bin/sh
set -eu

INSTALL_DIR="$HOME/.local/bin"
RELEASES_API_URL="https://api.github.com/repos/Heysh1n/sfc/releases"
API_URL="$RELEASES_API_URL/latest"
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
    PAD="    "

    printf "%s%s███████╗ ███████╗ ██████╗%s\n" "$PAD" "$BRIGHT_WHITE" "$RESET"
    printf "%s%s██╔════╝ ██╔════╝██╔════╝%s\n" "$PAD" "$WHITE" "$RESET"
    printf "%s%s███████╗ █████╗  ██║     %s\n" "$PAD" "$MAGENTA" "$RESET"
    printf "%s%s╚════██║ ██╔══╝  ██║     %s\n" "$PAD" "$BRIGHT_MAGENTA" "$RESET"
    printf "%s%s███████║ ██║     ╚██████╗%s\n" "$PAD" "$MAGENTA" "$RESET"
    printf "%s%s╚══════╝ ╚═╝      ╚═════╝%s\n" "$PAD" "$DIM_MAGENTA" "$RESET"
}

header() {
    clear 2>/dev/null || true

    PAD="    "

    printf "\n"
    printf "%s%s╭────────────────────────────────────────────╮%s\n" "$PAD" "$MAGENTA" "$RESET"
    printf "%s%s│%s               %sSFC Installer%s                %s│%s\n" "$PAD" "$MAGENTA" "$RESET" "$BOLD" "$RESET" "$MAGENTA" "$RESET"
    printf "%s%s╰────────────────────────────────────────────╯%s\n" "$PAD" "$MAGENTA" "$RESET"

    printf "\n"
    logo
    printf "\n"

    printf "%s      %sSmart File Collector%s\n" "$PAD" "$DIM" "$RESET"
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
normalize_version_input() {
    VERSION_INPUT="$1"

    case "$VERSION_INPUT" in
        "")
            printf "latest"
            ;;
        latest|LATEST)
            printf "latest"
            ;;
        v*)
            printf "%s" "$VERSION_INPUT"
            ;;
        [0-9]*)
            printf "v%s" "$VERSION_INPUT"
            ;;
        *)
            printf "%s" "$VERSION_INPUT"
            ;;
    esac
}

release_api_url() {
    REQUESTED_VERSION="$1"

    if [ "$REQUESTED_VERSION" = "latest" ]; then
        printf "%s" "$API_URL"
        return
    fi

    ENCODED_TAG="$(python3 - "$REQUESTED_VERSION" <<'PY'
from urllib.parse import quote
import sys

print(quote(sys.argv[1], safe=""))
PY
)"

    printf "%s/tags/%s" "$RELEASES_API_URL" "$ENCODED_TAG"
}

fetch_release_info() {
    REQUESTED_VERSION="$(normalize_version_input "${1:-latest}")"
    TMP_JSON="$(mktemp)"

    cleanup() {
        rm -f "$TMP_JSON"
    }

    trap cleanup EXIT INT TERM

    RELEASE_URL="$(release_api_url "$REQUESTED_VERSION")"

    if [ "$REQUESTED_VERSION" = "latest" ]; then
        info "Fetching latest release data..."
    else
        info "Fetching release data for $REQUESTED_VERSION..."
    fi

    if ! curl -fsSL -H "User-Agent: $USER_AGENT" "$RELEASE_URL" -o "$TMP_JSON"; then
        error "Failed to fetch release data"
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
        print("ERROR|release tag_name not found")
        sys.exit(1)

    expected_names = [f"sfc.{tag}.pyz", "sfc.pyz"]
    assets = data.get("assets", [])

    for expected_name in expected_names:
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

    wanted = " or ".join(expected_names)
    print(f"ERROR|{wanted} asset not found in release {tag}. Found: {asset_names}")
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

    success "Release: $TAG"
    success "Asset found: $ASSET_NAME"
}

# ── Install ────────────────────────────────────────────
install_sfc() {
    REQUESTED_VERSION="$(normalize_version_input "${1:-latest}")"

    require_cmd curl
    require_cmd python3

    header
    if [ "$REQUESTED_VERSION" = "latest" ]; then
        printf "%sInstalling / Updating SFC%s\n\n" "$BOLD" "$RESET"
    else
        printf "%sInstalling SFC %s%s\n\n" "$BOLD" "$REQUESTED_VERSION" "$RESET"
    fi

    fetch_release_info "$REQUESTED_VERSION"

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

install_specific_version() {
    header
    printf "%sInstall specific SFC version%s\n\n" "$BOLD" "$RESET"

    printf "Enter release tag/version, for example:\n"
    printf "  %sv4.9.0%s or %s4.9.0%s\n\n" "$BRIGHT_MAGENTA" "$RESET" "$BRIGHT_MAGENTA" "$RESET"
    printf "%sVersion:%s " "$BOLD" "$RESET"

    read -r VERSION_CHOICE

    if [ -z "$VERSION_CHOICE" ]; then
        warn "Cancelled"
        pause
        return
    fi

    install_sfc "$VERSION_CHOICE"
}

uninstall_sfc() {
    header
    printf "%sUninstall SFC%s\n\n" "$BOLD" "$RESET"

    info "Install path: $INSTALL_DIR/sfc"

    if [ ! -f "$INSTALL_DIR/sfc" ]; then
        warn "SFC is not installed at this path"
        pause
        return
    fi

    printf "\n"
    printf "%sRemove SFC from this system? [y/N]:%s " "$BOLD" "$RESET"
    read -r CONFIRM_REMOVE

    case "$CONFIRM_REMOVE" in
        y|Y|yes|YES)
            rm -f "$INSTALL_DIR/sfc"
            success "Removed $INSTALL_DIR/sfc"
            ;;
        *)
            info "Cancelled"
            ;;
    esac

    pause
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

        printf "  %s1%s) %sInstall / Update latest SFC%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s2%s) %sInstall specific version%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s3%s) %sShow install location%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s4%s) %sUninstall SFC%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s5%s) %sExit%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"

        printf "\n"
        printf "%sChoice:%s " "$BOLD" "$RESET"

        read -r ACTION

        case "$ACTION" in
            1)
                install_sfc latest
                printf "\n"
                exit 0
                ;;
            2)
                install_specific_version
                printf "\n"
                exit 0
                ;;
            3)
                show_location
                ;;
            4)
                uninstall_sfc
                ;;
            5|0|q|Q)
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
