#!/usr/bin/env bash
set -euo pipefail

APP_ID="gcode-lisa"

rm -f "$HOME/.local/share/applications/${APP_ID}.desktop"
rm -f "$HOME/.local/share/mime/packages/${APP_ID}-mime.xml"

update-desktop-database "$HOME/.local/share/applications" >/dev/null 2>&1 || true
update-mime-database "$HOME/.local/share/mime" >/dev/null 2>&1 || true

echo "Removed ${APP_ID} launcher and mime registration"
