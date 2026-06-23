#!/usr/bin/env bash
# One-time setup: download King County Assessor data extracts.
# These are public data files (~180MB zipped, ~880MB unzipped).
# They refresh weekly on KC's side; re-run before each appeal cycle.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
EXTRACTS_DIR="$SCRIPT_DIR/../extracts"

mkdir -p "$EXTRACTS_DIR"

BASE_URL="https://aqua.kingcounty.gov/extranet/assessor"

declare -A FILES=(
    ["Real Property Sales"]="EXTR_RPSale.csv"
    ["Residential Building"]="EXTR_ResBldg.csv"
    ["Real Property Account"]="EXTR_RPAcct_NoName.csv"
)

echo "=== King County Assessor Extract Setup ==="
echo "Download directory: $EXTRACTS_DIR"
echo ""

all_present=true
for name in "${!FILES[@]}"; do
    csv="${FILES[$name]}"
    if [ -f "$EXTRACTS_DIR/$csv" ]; then
        mod=$(stat -f "%Sm" -t "%Y-%m-%d" "$EXTRACTS_DIR/$csv" 2>/dev/null || date -r "$EXTRACTS_DIR/$csv" "+%Y-%m-%d" 2>/dev/null || echo "unknown")
        size=$(du -h "$EXTRACTS_DIR/$csv" | cut -f1)
        echo "  ✓ $csv ($size, $mod)"
    else
        echo "  ✗ $csv — downloading..."
        all_present=false
        encoded_name=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$name'))")
        curl -# -o "$EXTRACTS_DIR/${name// /_}.zip" "$BASE_URL/$encoded_name.zip"
        (cd "$EXTRACTS_DIR" && unzip -o "${name// /_}.zip" && rm "${name// /_}.zip")
        echo "  ✓ $csv downloaded"
    fi
done

echo ""
if [ "$all_present" = true ]; then
    echo "All extracts present. Run setup again to refresh."
else
    echo "Setup complete. Extracts ready."
fi
