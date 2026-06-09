#!/bin/sh
set -eu

# SFC Installer for Linux / macOS
# One-line install:
#   curl -fsSL https://raw.githubusercontent.com/Heysh1n/sfc/main/install.sh | sh

REPO="Heysh1n/sfc"
DOWNLOAD_URL="https://github.com/$REPO/releases/latest/download/sfc.pyz"
USER_AGENT="sfc-installer"

# ── Detect OS ──────────────────────────────────────────
OS_NAME="$(uname -s 2>/dev/null || printf 'unknown')"

case "$OS_NAME" in
    Linux)
        INSTALL_DIR="${SFC_INSTALL_DIR:-$HOME/.local/bin}"
        ;;
    Darwin)
        INSTALL_DIR="${SFC_INSTALL_DIR:-/usr/local/bin}"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        # Windows (Git Bash / MSYS2 / Cygwin) — show redirect and exit
        printf "\n"
        printf "  It looks like you are running Windows (Git Bash / MSYS2).\n"
        printf "  This installer is for Linux and macOS only.\n"
        printf "\n"
        printf "  For Windows, use PowerShell:\n"
        printf "\n"
        printf "    irm https://raw.githubusercontent.com/Heysh1n/sfc/main/install.ps1 | iex\n"
        printf "\n"
        exit 0
        ;;
    *)
        printf "\n"
        printf "  Unknown operating system: %s\n" "$OS_NAME"
        printf "  This installer supports Linux and macOS.\n"
        printf "\n"
        printf "  If you are on Windows, use PowerShell:\n"
        printf "\n"
        printf "    irm https://raw.githubusercontent.com/Heysh1n/sfc/main/install.ps1 | iex\n"
        printf "\n"
        exit 1
        ;;
esac

INSTALL_PATH="$INSTALL_DIR/sfc"

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
    printf "%s%s│%s              %sSFC Installer%s               %s│%s\n" "$PAD" "$MAGENTA" "$RESET" "$BOLD" "$RESET" "$MAGENTA" "$RESET"
    printf "%s%s╰────────────────────────────────────────────╯%s\n" "$PAD" "$MAGENTA" "$RESET"

    printf "\n"
    logo
    printf "\n"

    printf "%s      %sSmart File Collector%s\n" "$PAD" "$DIM" "$RESET"
    printf "\n"
}

pause() {
    printf "\n%sPress Enter to continue...%s" "$DIM" "$RESET"
    read -r _ || true
}

require_cmd() {
    if ! command -v "$1" >/dev/null 2>&1; then
        error "Required command not found: $1"
        exit 1
    fi
}

shell_profile_file() {
    SHELL_NAME="$(basename "${SHELL:-}")"

    if [ "$SHELL_NAME" = "zsh" ]; then
        printf "%s/.zshrc" "$HOME"
        return
    fi

    if [ "$SHELL_NAME" = "bash" ]; then
        if [ "$OS_NAME" = "Darwin" ]; then
            printf "%s/.bash_profile" "$HOME"
        else
            printf "%s/.bashrc" "$HOME"
        fi
        return
    fi

    if [ "$OS_NAME" = "Darwin" ]; then
        printf "%s/.zshrc" "$HOME"
    else
        printf "%s/.profile" "$HOME"
    fi
}

path_contains_install_dir() {
    case ":$PATH:" in
        *":$INSTALL_DIR:"*) return 0 ;;
        *) return 1 ;;
    esac
}

add_path_to_profile() {
    PROFILE_FILE="$(shell_profile_file)"
    PATH_LINE="export PATH=\"$INSTALL_DIR:\$PATH\""

    mkdir -p "$(dirname "$PROFILE_FILE")"
    touch "$PROFILE_FILE"

    if grep -F "$INSTALL_DIR" "$PROFILE_FILE" >/dev/null 2>&1; then
        warn "PATH entry already exists in $PROFILE_FILE"
        return
    fi

    {
        printf "\n"
        printf "# SFC\n"
        printf "%s\n" "$PATH_LINE"
    } >> "$PROFILE_FILE"

    success "Added $INSTALL_DIR to PATH in $PROFILE_FILE"
    warn "Restart terminal or run: . $PROFILE_FILE"
}

# ── Install ────────────────────────────────────────────
install_sfc() {
    header
    printf "%sInstalling / Updating SFC%s\n\n" "$BOLD" "$RESET"

    require_cmd curl

    info "Platform: $OS_NAME"
    info "Install path: $INSTALL_PATH"

    # macOS: /usr/local/bin может потребовать sudo
    if [ "$OS_NAME" = "Darwin" ] && [ ! -w "$INSTALL_DIR" ]; then
        warn "$INSTALL_DIR is not writable — trying with sudo"
        mkdir -p "$INSTALL_DIR" 2>/dev/null || sudo mkdir -p "$INSTALL_DIR"
        USE_SUDO=1
    else
        mkdir -p "$INSTALL_DIR"
        USE_SUDO=0
    fi

    TMP_FILE="$(mktemp 2>/dev/null || printf "%s/sfc.tmp" "$INSTALL_DIR")"

    cleanup_tmp() {
        rm -f "$TMP_FILE" 2>/dev/null || true
    }

    trap cleanup_tmp EXIT INT TERM

    info "Downloading latest release..."

    if ! curl -fL --retry 3 --connect-timeout 15 -H "User-Agent: $USER_AGENT" "$DOWNLOAD_URL" -o "$TMP_FILE"; then
        error "Failed to download SFC"
        printf "\n"
        printf "Expected release asset:\n"
        printf "  %ssfc.pyz%s\n" "$BRIGHT_MAGENTA" "$RESET"
        printf "\n"
        printf "Expected URL:\n"
        printf "  https://github.com/%s/releases/latest/download/sfc.pyz\n" "$REPO"
        exit 1
    fi

    if [ "$USE_SUDO" = "1" ]; then
        sudo mv "$TMP_FILE" "$INSTALL_PATH"
        sudo chmod +x "$INSTALL_PATH"
    else
        mv "$TMP_FILE" "$INSTALL_PATH"
        chmod +x "$INSTALL_PATH"
    fi

    trap - EXIT INT TERM

    printf "\n"
    line
    success "SFC installed successfully"
    line
    printf "\n"

    if path_contains_install_dir && command -v sfc >/dev/null 2>&1; then
        printf "%sRun:%s\n" "$BOLD" "$RESET"
        printf "  %ssfc%s\n" "$BRIGHT_MAGENTA" "$RESET"
        return
    fi

    if path_contains_install_dir; then
        printf "%sRun after restarting terminal:%s\n" "$BOLD" "$RESET"
        printf "  %ssfc%s\n" "$BRIGHT_MAGENTA" "$RESET"
        return
    fi

    warn "$INSTALL_DIR is not in your PATH"
    printf "\n"

    printf "%sAdd it automatically? [Y/n]:%s " "$BOLD" "$RESET"
    read -r ADD_PATH || ADD_PATH=""

    case "$ADD_PATH" in
        n|N|no|NO)
            printf "\n"
            printf "%sManual command:%s\n" "$BOLD" "$RESET"
            printf "  export PATH=\"%s:\$PATH\"\n" "$INSTALL_DIR"
            printf "\n"
            printf "%sDirect run:%s\n" "$BOLD" "$RESET"
            printf "  %s\n" "$INSTALL_PATH"
            ;;
        *)
            add_path_to_profile
            printf "\n"
            printf "%sDirect run now:%s\n" "$BOLD" "$RESET"
            printf "  %s\n" "$INSTALL_PATH"
            ;;
    esac
}

uninstall_sfc() {
    header
    printf "%sUninstall SFC%s\n\n" "$BOLD" "$RESET"

    info "Install path: $INSTALL_PATH"

    if [ ! -f "$INSTALL_PATH" ]; then
        warn "SFC is not installed at this path"
        pause
        return
    fi

    printf "\n"
    printf "%sRemove SFC from this system? [y/N]:%s " "$BOLD" "$RESET"
    read -r CONFIRM_REMOVE || CONFIRM_REMOVE=""

    case "$CONFIRM_REMOVE" in
        y|Y|yes|YES)
            if [ "$OS_NAME" = "Darwin" ] && [ ! -w "$INSTALL_PATH" ]; then
                sudo rm -f "$INSTALL_PATH"
            else
                rm -f "$INSTALL_PATH"
            fi
            success "Removed $INSTALL_PATH"
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

    info "Platform: $OS_NAME"
    info "$INSTALL_PATH"

    if [ -f "$INSTALL_PATH" ]; then
        success "SFC is installed"
    else
        warn "SFC is not installed yet"
    fi

    printf "\n"
    printf "%sPATH status:%s\n" "$BOLD" "$RESET"

    if path_contains_install_dir; then
        success "$INSTALL_DIR is in PATH"
    else
        warn "$INSTALL_DIR is not in PATH"
    fi

    pause
}

show_menu() {
    while :; do
        header

        printf "%sSelect action:%s\n\n" "$BOLD" "$RESET"

        printf "  %s1%s) %sInstall / Update SFC locally%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s2%s) %sShow install location%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s3%s) %sUninstall SFC%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"
        printf "  %s4%s) %sExit%s\n" "$BRIGHT_MAGENTA" "$RESET" "$WHITE" "$RESET"

        printf "\n"
        printf "%sChoice:%s " "$BOLD" "$RESET"

        read -r ACTION || ACTION="4"

        case "$ACTION" in
            1)
                install_sfc
                printf "\n"
                exit 0
                ;;
            2)
                show_location
                ;;
            3)
                uninstall_sfc
                ;;
            4|0|q|Q)
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

case "${1:-}" in
    install|update|--install|-i)
        install_sfc
        ;;
    uninstall|remove|--uninstall)
        uninstall_sfc
        ;;
    location|path|--location|--path)
        show_location
        ;;
    help|--help|-h)
        printf "SFC Installer\n\n"
        printf "Usage:\n"
        printf "  sh install.sh              Open menu\n"
        printf "  sh install.sh install      Install / update\n"
        printf "  sh install.sh uninstall    Uninstall\n"
        printf "  sh install.sh location     Show install location\n"
        ;;
    "")
        show_menu
        ;;
    *)
        error "Unknown option: $1"
        printf "Run: sh install.sh --help\n"
        exit 1
        ;;
esac
