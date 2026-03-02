#!/usr/bin/env bash
#
# Package the Anki addon into a .ankiaddon file.
#
# .ankiaddon is a zip archive containing the addon files at the top level
# (no parent directory). __pycache__ folders must be excluded.
#
# Usage: ./package_addon.sh [output_name]
#   output_name  - optional, defaults to the package name from manifest.json

set -euo pipefail

ADDON_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_DIR="$(dirname "$ADDON_DIR")"

# Read package name from manifest.json
PACKAGE_NAME=$(python3 -c "import json, sys; print(json.load(open(sys.argv[1]))['package'])" "$ADDON_DIR/manifest.json")

TIMESTAMP=$(date +"%Y-%m-%d")

OUTPUT_NAME="${1:-$PACKAGE_NAME}-${TIMESTAMP}.ankiaddon"
OUTPUT_PATH="$REPO_DIR/$OUTPUT_NAME"

# Create the .ankiaddon zip from inside the addon directory
# - Exclude __pycache__, .DS_Store, and other unwanted files
cd "$ADDON_DIR"
zip -r "$OUTPUT_PATH" . \
    -x "__pycache__/*" \
    -x "*/__pycache__/*" \
    -x ".DS_Store" \
    -x "*/.DS_Store" \
    -x "dev_sync.py"

echo ""
echo "Packaged: $OUTPUT_PATH"
echo "Contents:"
unzip -l "$OUTPUT_PATH"
