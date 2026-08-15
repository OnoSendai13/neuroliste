#!/bin/bash
# Local multi-platform build script for Neuroliste
# Usage: ./scripts/build-all-platforms.sh [platform]
# Platforms: linux, windows, macos, all (default)

set -e

PLATFORM=${1:-all}
REPO_ROOT=$(cd "$(dirname "$0")/.." && pwd)
cd "$REPO_ROOT"

echo "Building Neuroliste for platform: $PLATFORM"
echo "Repo root: $REPO_ROOT"

# Install root dependencies
echo "Installing root dependencies..."
npm ci

# Build frontend
echo "Building frontend..."
cd frontend
npm ci
npm run build
cd ..

# Build for requested platform(s)
build_linux() {
    echo "=== Building Linux (AppImage) ==="
    npm run electron:build
    echo "Linux build complete: dist-electron/*.AppImage"
}

build_windows() {
    echo "=== Building Windows (NSIS) ==="
    # On Windows, run: npm run electron:build -- --win
    # On Linux/macOS with Wine, you can try cross-compilation but it's complex
    echo "Windows build must run on Windows or via CI"
    echo "Run on Windows: npm run electron:build -- --win"
}

build_macos() {
    echo "=== Building macOS (DMG) ==="
    # On macOS, run: npm run electron:build -- --mac
    # On Linux, cross-compilation requires macOS SDK which is not legal without Apple hardware
    echo "macOS build must run on macOS or via CI"
    echo "Run on macOS: npm run electron:build -- --mac"
}

case $PLATFORM in
    linux)
        build_linux
        ;;
    windows)
        build_windows
        ;;
    macos)
        build_macos
        ;;
    all)
        build_linux
        build_windows
        build_macos
        ;;
    *)
        echo "Unknown platform: $PLATFORM"
        echo "Usage: $0 [linux|windows|macos|all]"
        exit 1
        ;;
esac

echo "Done!"