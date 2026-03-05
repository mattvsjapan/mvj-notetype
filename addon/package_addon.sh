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
VERSION=$(date +"%Y.%m.%d")

# Update version in manifest.json
python3 -c "
import json, sys
path = sys.argv[1]
with open(path) as f:
    m = json.load(f)
m['version'] = sys.argv[2]
with open(path, 'w') as f:
    json.dump(m, f, indent=4)
    f.write('\n')
" "$ADDON_DIR/manifest.json" "$VERSION"

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
    -x "dev_sync.py" \
    -x "dev_migrate.py"

echo ""
echo "Packaged: $OUTPUT_PATH"
echo "Contents:"
unzip -l "$OUTPUT_PATH"
