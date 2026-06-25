#!/usr/bin/env bash
# Build a single-file standalone binary of the agent using PyInstaller,
# for one or more target platforms. Also writes SHA256SUMS so the
# install-via-curl scripts can verify integrity.
#
# Usage:
#   ./scripts/build_agent_binary.sh                       # auto-detect host
#   ./scripts/build_agent_binary.sh --target linux        # explicit
#   ./scripts/build_agent_binary.sh --target all          # build all 3
#
# Targets:
#   linux   : dist/agent-linux-x86_64
#   macos   : dist/agent-darwin-x86_64, dist/agent-darwin-arm64
#   windows : dist/agent-windows-x86_64.exe
#
# After build, attach `dist/agent-*` and `dist/SHA256SUMS` to a GitHub
# Release. The install-via-curl script downloads from
# $UEBA_RELEASE_URL/agent-$TARGET-$ARCH and verifies against SHA256SUMS.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_DIR}"

VERSION="${UEBA_VERSION:-$(grep -m1 '^version' pyproject.toml | sed -E 's/version *= *"([^"]+)"/\1/')}"
DIST_DIR="${REPO_DIR}/dist"
TARGET="auto"
ARCH="$(uname -m)"

usage() {
    cat <<EOF
Usage: $0 [--target linux|macos|windows|all|auto] [--arch x86_64|arm64]

Targets:
  auto     (default) — build for the current host only
  linux    — Linux x86_64
  macos    — macOS x86_64 + arm64 (universal not built; build on macOS)
  windows  — Windows x86_64 (must build on Windows; cannot cross-compile)
  all      — try all 3 (will skip ones the host can't build)

Options:
  --arch {x86_64|arm64}    target CPU architecture (default: host's)
  --version VERSION        override version (default: from pyproject.toml)
  -h, --help               show this help
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --target) TARGET="$2"; shift 2 ;;
        --arch)   ARCH="$2"; shift 2 ;;
        --version) VERSION="$2"; shift 2 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "unknown arg: $1" >&2; usage; exit 2 ;;
    esac
done

log() { echo "[build-binary] $*" >&2; }

detect_target() {
    case "$(uname -s)" in
        Linux*)   echo "linux" ;;
        Darwin*)  echo "macos" ;;
        MINGW*|CYGWIN*|MSYS*) echo "windows" ;;
        *)        echo "unknown" ;;
    esac
}

if [[ "$TARGET" == "auto" ]]; then
    TARGET="$(detect_target)"
    log "Auto-detected target: $TARGET"
fi

# PyInstaller build: pure-Python — no native extensions, so we can build for
# the HOST OS. Cross-compiling to a different OS requires running PyInstaller
# ON that OS (or in a Docker image of it). For demo we just build the host.
build_one() {
    local os="$1"
    local arch="$2"
    local out_name="agent-${os}-${arch}"
    local ext=""
    [[ "$os" == "windows" ]] && ext=".exe"
    local out_path="${DIST_DIR}/${out_name}${ext}"

    log "Building ${out_name}${ext}"
    rm -rf "${REPO_DIR}/build" "${out_path}"
    pyinstaller \
        --name "agent-${os}-${arch}" \
        --onefile \
        --console \
        --paths src \
        --collect-submodules agent \
        --collect-submodules httpx \
        --collect-submodules pydantic \
        --collect-submodules pydantic_settings \
        --copy-metadata pydantic \
        --copy-metadata pydantic_settings \
        --hidden-import pydantic_settings \
        --exclude-module pandas --exclude-module numpy --exclude-module scipy \
        --exclude-module sklearn --exclude-module joblib --exclude-module matplotlib \
        --exclude-module fastapi --exclude-module uvicorn --exclude-module starlette \
        --exclude-module PyQt5 --exclude-module PyQt6 \
        --exclude-module PySide2 --exclude-module PySide6 \
        --exclude-module wx --exclude-module gtk \
        --exclude-module IPython --exclude-module jupyter --exclude-module notebook \
        --exclude-module pytest \
        src/agent/cli.py 2>&1 | tail -3

    # PyInstaller writes to ./dist/agent-{os}-{arch}{.exe}
    if [[ ! -f "${REPO_DIR}/dist/${out_name}${ext}" ]]; then
        log "ERROR: expected ${out_path} not produced"
        return 1
    fi
    log "Built: ${out_path} ($(du -h "${out_path}" | cut -f1))"
}

# --- Main -----------------------------------------------------------------

log "Installing PyInstaller"
python3 -m pip install --quiet --upgrade 'pyinstaller>=6.0'

mkdir -p "${DIST_DIR}"
rm -f "${DIST_DIR}/SHA256SUMS"

case "$TARGET" in
    linux)
        build_one linux "${ARCH}" ;;
    macos)
        build_one darwin x86_64
        # arm64 only on Apple Silicon; if we can't build it, skip.
        if [[ "$(uname -m)" == "arm64" ]] || command -v arch >/dev/null 2>&1; then
            build_one darwin arm64 || log "WARN: darwin-arm64 build failed (skipping)"
        else
            log "Skipping darwin-arm64 (build on Apple Silicon to enable)"
        fi
        ;;
    windows)
        build_one windows "${ARCH}" ;;
    all)
        log "Building all 3 (will skip those the host can't produce)"
        if [[ "$(uname -s)" == "Linux" ]]; then
            build_one linux "${ARCH}"
        elif [[ "$(uname -s)" == "Darwin" ]]; then
            build_one darwin x86_64
            build_one darwin arm64
        fi
        if [[ "$(uname -s)" == "MINGW"* ]] || [[ "$(uname -s)" == "MSYS"* ]]; then
            build_one windows "${ARCH}"
        fi
        log "Done. To build for OTHER OSes, run this script on that host."
        ;;
    *)
        die "Unknown target: $TARGET"
        ;;
esac

# Write SHA256SUMS for everything in dist/ (except itself + old builds).
log "Writing SHA256SUMS"
cd "${DIST_DIR}"
for f in agent-*; do
    if [[ -f "$f" && "$f" != "SHA256SUMS" ]]; then
        sha256sum "$f" >> SHA256SUMS
    fi
done
cd - >/dev/null
cat "${DIST_DIR}/SHA256SUMS"

cat <<EOF

============================================================
  Standalone agent binary built (version ${VERSION}).
============================================================

Files in dist/:
EOF
ls -lh "${DIST_DIR}"/agent-* 2>/dev/null | awk '{print "  " $9 " (" $5 ")"}'
cat <<EOF

Publish to GitHub Releases (or your artifact store):

  gh release create v${VERSION} \\
      dist/agent-linux-x86_64 \\
      dist/agent-darwin-x86_64 \\
      dist/agent-darwin-arm64 \\
      dist/agent-windows-x86_64.exe \\
      dist/SHA256SUMS \\
      --title "UEBA Agent v${VERSION}" \\
      --notes "Release notes here."

Then employees install with ONE line:

  # Linux
  curl -sSL https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download/install.sh | sudo bash -s -- \\
      --server-url https://ueba.corp.example

  # macOS
  curl -sSL https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download/install.sh | sudo bash -s -- \\
      --server-url https://ueba.corp.example

  # Windows (PowerShell)
  iwr https://github.com/vespionage/ueba-endpoint-monitoring/releases/latest/download/install.ps1 -useb | iex

============================================================
EOF
