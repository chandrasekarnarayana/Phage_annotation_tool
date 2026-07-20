#!/usr/bin/env bash
# Builds a self-contained .deb package for Phage Annotator.
#
# The Python runtime and all scientific-stack dependencies are bundled via
# PyInstaller inside a Debian 11 (glibc 2.31) container for broad
# compatibility, so the resulting package only depends on system Qt/X11
# libraries that are normally already present on any Linux desktop.
#
# Usage:
#   packaging/deb/build.sh
#
# Output:
#   dist/phage-annotator_<version>_amd64.deb

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEB_DIR="$ROOT_DIR/packaging/deb"
WORK_DIR="$DEB_DIR/build"
DIST_DIR="$ROOT_DIR/dist"
IMAGE_TAG="phage-annotator-pyinstaller-build"

VERSION="$(grep -m1 '^version = ' "$ROOT_DIR/pyproject.toml" | sed -E 's/version = "(.*)"/\1/')"
if [ -z "$VERSION" ]; then
    echo "Could not determine version from pyproject.toml" >&2
    exit 1
fi
echo "Building phage-annotator ${VERSION} (amd64) .deb ..."

rm -rf "$WORK_DIR"
mkdir -p "$WORK_DIR" "$DIST_DIR"

echo "==> Building PyInstaller bundle (this takes a few minutes the first time)"
docker build -f "$DEB_DIR/Dockerfile.build" -t "$IMAGE_TAG" "$ROOT_DIR"

echo "==> Extracting bundle from build image"
CONTAINER_ID="$(docker create "$IMAGE_TAG")"
trap 'docker rm -f "$CONTAINER_ID" >/dev/null 2>&1 || true' EXIT

PKG_ROOT="$WORK_DIR/pkgroot"
mkdir -p "$PKG_ROOT/opt" "$PKG_ROOT/usr/bin" "$PKG_ROOT/usr/share/applications" \
    "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps" "$PKG_ROOT/DEBIAN"

docker cp "$CONTAINER_ID:/build/dist/phage-annotator" "$PKG_ROOT/opt/phage-annotator"
docker rm -f "$CONTAINER_ID" >/dev/null
trap - EXIT

echo "==> Assembling package tree"
ln -s /opt/phage-annotator/phage-annotator "$PKG_ROOT/usr/bin/phage-annotator"
cp "$DEB_DIR/phage-annotator.desktop" "$PKG_ROOT/usr/share/applications/phage-annotator.desktop"
cp "$DEB_DIR/phage-annotator.png" "$PKG_ROOT/usr/share/icons/hicolor/256x256/apps/phage-annotator.png"

INSTALLED_SIZE_KB="$(du -sk "$PKG_ROOT/opt" | cut -f1)"
sed \
    -e "s/__VERSION__/${VERSION}/" \
    -e "s/__INSTALLED_SIZE__/${INSTALLED_SIZE_KB}/" \
    "$DEB_DIR/control.template" > "$PKG_ROOT/DEBIAN/control"

chmod -R go-w "$PKG_ROOT"
find "$PKG_ROOT" -type d -exec chmod 755 {} +

OUT_DEB="$DIST_DIR/phage-annotator_${VERSION}_amd64.deb"
echo "==> Building ${OUT_DEB}"
dpkg-deb --build --root-owner-group "$PKG_ROOT" "$OUT_DEB"

echo "==> Verifying package"
dpkg-deb --info "$OUT_DEB"
echo
echo "Done: $OUT_DEB"
echo "Install with: sudo apt install $OUT_DEB   (or: sudo dpkg -i $OUT_DEB && sudo apt -f install)"
