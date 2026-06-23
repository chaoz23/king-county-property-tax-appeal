#!/usr/bin/env bash
# Download King County Assessor data extracts.
#
# The extracts are behind a JavaScript disclaimer at:
#   https://info.kingcounty.gov/assessor/datadownload/default.aspx
#
# This script opens the download page in Safari. The user must:
# 1. Check the disclaimer checkbox
# 2. Download: Real Property Sales, Residential Building, Real Property Account
# 3. Move/copy the CSVs to the extracts directory below.
#
# Extracts refresh weekly on the KC side; re-download before each appeal run.

set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
EXTRACTS_DIR="$SKILL_DIR/extracts"

mkdir -p "$EXTRACTS_DIR"

echo "=== King County Assessor Extract Download ==="
echo ""
echo "Extracts directory: $EXTRACTS_DIR"
echo ""

# Check what we already have
for f in EXTR_RPSale.csv EXTR_ResBldg.csv EXTR_RPAcct_NoName.csv; do
    if [ -f "$EXTRACTS_DIR/$f" ]; then
        mod=$(stat -f "%Sm" -t "%Y-%m-%d" "$EXTRACTS_DIR/$f" 2>/dev/null || date -r "$EXTRACTS_DIR/$f" "+%Y-%m-%d" 2>/dev/null)
        size=$(du -h "$EXTRACTS_DIR/$f" | cut -f1)
        echo "  ✓ $f ($size, modified $mod)"
    else
        echo "  ✗ $f — MISSING"
    fi
done

echo ""
echo "Opening the KC Assessor data download page..."
echo "Steps:"
echo "  1. Check the disclaimer checkbox"
echo "  2. Download these files and save to: $EXTRACTS_DIR"
echo "     - Real Property Sales  → EXTR_RPSale.csv"
echo "     - Residential Building → EXTR_ResBldg.csv"
echo "     - Real Property Account (no names) → EXTR_RPAcct_NoName.csv"
echo ""

open "https://info.kingcounty.gov/assessor/datadownload/default.aspx" 2>/dev/null || echo "Open the URL manually in your browser."
