#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"

VERSION="1.0.4"
ARCH="$(uname -m)"
VENV=".build-venv-mac"
BACKEND_DIR="dist/AutohomeSpecExporter"
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

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp packaging/macos/Info.plist "$APP/Contents/Info.plist"
clang -O2 -Wall -Wextra -framework Cocoa -o "$APP/Contents/MacOS/AutohomeSpecExporter" packaging/macos/launcher.m
cp packaging/macos/launcher.sh "$APP/Contents/MacOS/launcher.sh"
chmod +x "$APP/Contents/MacOS/AutohomeSpecExporter" "$APP/Contents/MacOS/launcher.sh"
cp assets/icon.icns "$APP/Contents/Resources/icon.icns"
ditto "$BACKEND_DIR" "$APP/Contents/Resources/backend"
printf 'APPL????' > "$APP/Contents/PkgInfo"
plutil -lint "$APP/Contents/Info.plist"

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
