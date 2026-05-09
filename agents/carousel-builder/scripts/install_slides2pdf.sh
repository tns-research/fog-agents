#!/usr/bin/env bash
#
# install_slides2pdf.sh - install the slides2pdf CLI for carousel-builder.
#
# Strategy (try in order, stop at first success):
#   1. If `slides2pdf` is already on PATH, do nothing.
#   2. Try to download a prebuilt binary from the latest GitHub release.
#   3. Try `go build` from source.
#   4. Print clear instructions for the Playwright fallback path.
#
# Output: writes the binary to $INSTALL_DIR (default /usr/local/bin if writable,
# else $HOME/.local/bin). Exits 0 on success, 2 on full fallback (so the agent
# can branch to Playwright).

set -euo pipefail

REPO_URL="https://github.com/the20100/simple-slides2pdf.git"
RELEASES_API="https://api.github.com/repos/the20100/simple-slides2pdf/releases/latest"
BIN_NAME="slides2pdf"

# Pick install dir
if [ -w "/usr/local/bin" ]; then
  INSTALL_DIR="/usr/local/bin"
else
  INSTALL_DIR="${HOME}/.local/bin"
  mkdir -p "${INSTALL_DIR}"
  case ":${PATH}:" in
    *":${INSTALL_DIR}:"*) ;;
    *) echo "WARNING: ${INSTALL_DIR} is not on PATH. Add it to your shell rc."  >&2 ;;
  esac
fi

# 1) Already installed?
if command -v "${BIN_NAME}" >/dev/null 2>&1; then
  echo "OK: slides2pdf already installed at $(command -v ${BIN_NAME})"
  exit 0
fi

# Detect platform
OS="$(uname -s | tr '[:upper:]' '[:lower:]')"
ARCH="$(uname -m)"
case "${ARCH}" in
  x86_64|amd64) ARCH="amd64" ;;
  arm64|aarch64) ARCH="arm64" ;;
  *) echo "WARNING: unsupported arch ${ARCH}, will try go build" >&2 ;;
esac

# 2) Try prebuilt binary from GitHub releases
try_prebuilt() {
  command -v curl >/dev/null 2>&1 || return 1
  command -v jq   >/dev/null 2>&1 || return 1

  echo "Trying prebuilt release for ${OS}/${ARCH}..."
  asset_url="$(curl -fsSL "${RELEASES_API}" 2>/dev/null \
    | jq -r --arg os "${OS}" --arg arch "${ARCH}" \
        '.assets[]? | select((.name | test($os)) and (.name | test($arch))) | .browser_download_url' \
    | head -n1 || true)"

  if [ -z "${asset_url}" ] || [ "${asset_url}" = "null" ]; then
    echo "  no matching release asset found"
    return 1
  fi

  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' RETURN
  echo "  downloading ${asset_url}"
  if ! curl -fsSL "${asset_url}" -o "${tmp}/payload"; then
    echo "  download failed"
    return 1
  fi

  case "${asset_url}" in
    *.tar.gz|*.tgz) tar -xzf "${tmp}/payload" -C "${tmp}" ;;
    *.zip)          unzip -q "${tmp}/payload" -d "${tmp}" ;;
    *)              cp "${tmp}/payload" "${tmp}/${BIN_NAME}" ;;
  esac

  bin_path="$(find "${tmp}" -type f -name "${BIN_NAME}" -perm -u+x -o -name "${BIN_NAME}" | head -n1)"
  if [ -z "${bin_path}" ]; then
    echo "  binary not found in archive"
    return 1
  fi

  install -m 0755 "${bin_path}" "${INSTALL_DIR}/${BIN_NAME}"
  echo "OK: installed prebuilt to ${INSTALL_DIR}/${BIN_NAME}"
  return 0
}

# 3) Try go build from source
try_go_build() {
  command -v go >/dev/null 2>&1 || { echo "Go not available, skipping source build"; return 1; }

  echo "Trying go build from source..."
  tmp="$(mktemp -d)"
  trap 'rm -rf "${tmp}"' RETURN
  if ! git clone --depth 1 "${REPO_URL}" "${tmp}/src" 2>/dev/null; then
    echo "  git clone failed"
    return 1
  fi
  ( cd "${tmp}/src" && go build -o "${tmp}/${BIN_NAME}" . ) || { echo "  go build failed"; return 1; }
  install -m 0755 "${tmp}/${BIN_NAME}" "${INSTALL_DIR}/${BIN_NAME}"
  echo "OK: built from source to ${INSTALL_DIR}/${BIN_NAME}"
  return 0
}

if try_prebuilt; then exit 0; fi
if try_go_build; then exit 0; fi

cat >&2 <<EOF

slides2pdf could not be installed (no prebuilt for this platform, no Go toolchain).

The agent will fall back to the Playwright pipeline:
  python -m venv .venv && source .venv/bin/activate
  pip install -r $(dirname "$0")/requirements.txt
  playwright install chromium

Both paths produce the same output filenames (carousel.pdf, slide-NN.png).
EOF
exit 2
