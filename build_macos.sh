#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

VERSION="1.0.2"
ARCH="$(uname -m)"
VENV=".build-venv-mac"
APP="dist/AutohomeSpecExporter.app"
DMG="dist/AutohomeSpecExporter_macOS_${ARCH}_v${VERSION}.dmg"
ZIP="dist/AutohomeSpecExporter_macOS_${ARCH}_v${VERSION}.zip"

if [ ! -x "$VENV/bin/python" ]; then
  python3 -m venv "$VENV"
fi

"$VENV/bin/python" -m pip install --upgrade pip
"$VENV/bin/python" -m pip install -r requirements-build.txt
"$VENV/bin/python" packaging/embed_web_assets.py
"$VENV/bin/python" -m unittest discover -s tests -v
"$VENV/bin/python" -m PyInstaller --clean --noconfirm packaging/autohome_exporter_macos.spec

codesign --force --deep --sign - "$APP"
codesign --verify --deep --strict --verbose=2 "$APP"

STAGING="dist/dmg-staging"
rm -rf "$STAGING"
mkdir -p "$STAGING"
ditto "$APP" "$STAGING/AutohomeSpecExporter.app"
ln -s /Applications "$STAGING/Applications"

rm -f "$DMG" "$ZIP"
hdiutil create \
  -volname "汽车之家配置采集器" \
  -srcfolder "$STAGING" \
  -ov \
  -format UDZO \
  "$DMG"
ditto -c -k --sequesterRsrc --keepParent "$APP" "$ZIP"

echo "macOS build completed:"
echo "  Architecture: $ARCH"
echo "  App: $APP"
echo "  DMG: $DMG"
echo "  ZIP: $ZIP"
