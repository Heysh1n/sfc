#!/usr/bin/env bash
set -euo pipefail

GITHUB_API="https://api.github.com/repos/Heysh1n/sfc/releases/latest"
ASSET_NAME="sfc.pyz"
TARGET_DIR="${HOME}/.local/bin"
TARGET="${TARGET_DIR}/sfc"
tmp=""

cleanup() {
  if [[ -n "${tmp}" ]]; then
    rm -f "${tmp}"
  fi
}
trap cleanup EXIT

latest_asset_url() {
  curl -fsSL -H "User-Agent: sfc-updater" "${GITHUB_API}" |
    python3 -c '
import json
import sys

asset_name = sys.argv[1]
release = json.load(sys.stdin)

for asset in release.get("assets", []):
    if asset.get("name") == asset_name:
        print(asset.get("browser_download_url", ""))
        raise SystemExit(0)

raise SystemExit(f"{asset_name} not found in latest release")
' "${ASSET_NAME}"
}

install_local() {
  if ! command -v curl >/dev/null 2>&1; then
    echo "curl not found"
    exit 1
  fi
  if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 not found"
    exit 1
  fi

  url="$(latest_asset_url)"
  if [[ -z "${url}" ]]; then
    echo "browser_download_url not found for ${ASSET_NAME}"
    exit 1
  fi

  mkdir -p "${TARGET_DIR}"
  tmp="${TARGET}.tmp"
  rm -f "${tmp}"
  curl -fL -H "User-Agent: sfc-updater" "${url}" -o "${tmp}"
  mv "${tmp}" "${TARGET}"
  tmp=""
  chmod +x "${TARGET}"
  echo "SFC installed: ${TARGET}"
}

PS3="Select action: "
options=(
  "Install SFC locally"
  "Exit"
)

select option in "${options[@]}"; do
  case "${REPLY}" in
    1)
      install_local
      break
      ;;
    2)
      echo "Exit"
      break
      ;;
    *)
      echo "Invalid selection"
      ;;
  esac
done
