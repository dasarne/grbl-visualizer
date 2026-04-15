#!/usr/bin/env bash
set -euo pipefail

APP_ID="gcode-lisa"
APP_NAME="GCode Lisa"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
ICON_PATH="$ROOT_DIR/assets/Lisa.svg"
DESKTOP_FILE="$ROOT_DIR/scripts/${APP_ID}.desktop"
MIME_XML="$ROOT_DIR/scripts/${APP_ID}-mime.xml"

mkdir -p "$HOME/.local/share/applications"
mkdir -p "$HOME/.local/share/mime/packages"

cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=${APP_NAME}
Comment=Cut with confidence. Waste less.
Exec=${ROOT_DIR}/.venv/bin/python -m src.main %f
Icon=${ICON_PATH}
Terminal=false
Categories=Development;Graphics;
MimeType=text/x-gcode-lisa;
EOF

cat > "$MIME_XML" <<EOF
<?xml version="1.0" encoding="UTF-8"?>
<mime-info xmlns="http://www.freedesktop.org/standards/shared-mime-info">
  <mime-type type="text/x-gcode-lisa">
    <comment>GCode program</comment>
    <glob pattern="*.gcode"/>
    <glob pattern="*.nc"/>
  </mime-type>
</mime-info>
EOF

install -m 0644 "$DESKTOP_FILE" "$HOME/.local/share/applications/${APP_ID}.desktop"
install -m 0644 "$MIME_XML" "$HOME/.local/share/mime/packages/${APP_ID}-mime.xml"

update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1 || true
xdg-mime default "${APP_ID}.desktop" text/x-gcode-lisa || true

echo "Installed ${APP_NAME} launcher and file associations for *.gcode and *.nc"
