#!/bin/bash
set -e

INSTALL_DIR="$HOME/.local/bin"
API_URL="https://api.github.com/repos/Heysh1n/sfc/releases/latest"
USER_AGENT="sfc-installer"

echo "=== SFC Installer ==="
PS3="Select action: "
options=("Install SFC locally" "Exit")

select opt in "${options[@]}"; do
    case "$REPLY" in
        1)
            echo "Fetching latest release data..."

            TMP_JSON=$(mktemp)
            curl -sS -H "User-Agent: $USER_AGENT" "$API_URL" -o "$TMP_JSON"

            DOWNLOAD_URL=$(python3 -c "
import json
import sys

try:
    with open('$TMP_JSON') as f:
        data = json.load(f)

    assets = data.get('assets', [])
    urls = [
        asset['browser_download_url']
        for asset in assets
        if asset.get('name') == 'sfc.pyz' and asset.get('browser_download_url')
    ]

    if urls:
        print(urls[0])
    else:
        print('ERROR: sfc.pyz asset not found in latest release')
except Exception as e:
    print(f'ERROR: Failed to parse GitHub API response ({e})')
")
            rm -f "$TMP_JSON"

            if [[ "$DOWNLOAD_URL" == ERROR* ]] || [[ -z "$DOWNLOAD_URL" ]]; then
                echo "$DOWNLOAD_URL"
                exit 1
            fi

            echo "Downloading sfc.pyz..."
            mkdir -p "$INSTALL_DIR"
            curl -sL -H "User-Agent: $USER_AGENT" "$DOWNLOAD_URL" -o "$INSTALL_DIR/sfc"
            chmod +x "$INSTALL_DIR/sfc"

            echo "============================================="
            echo "Successfully installed to $INSTALL_DIR/sfc"
            echo "Make sure $INSTALL_DIR is in your PATH"
            echo "============================================="
            break
            ;;
        2)
            echo "Exit."
            exit 0
            ;;
        *)
            echo "Invalid option. Try again."
            ;;
    esac
done
