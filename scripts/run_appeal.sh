#!/usr/bin/env bash
# Run the full appeal pipeline for an address.
# Usage: ./scripts/run_appeal.sh "1817 Morris Ave S, Renton, WA 98055"

set -euo pipefail

if [ $# -lt 1 ]; then
    echo "Usage: $0 <address>"
    echo "Example: $0 \"1817 Morris Ave S, Renton, WA 98055\""
    exit 1
fi

ADDRESS="$1"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$SCRIPT_DIR/.."

# Check extracts
if [ ! -f "$PROJECT_DIR/extracts/EXTR_RPSale.csv" ]; then
    echo "Extracts not found. Running setup..."
    bash "$SCRIPT_DIR/setup.sh"
fi

# Stage 1: Resolve parcel
echo ""
echo "═══ Stage 1: Resolving parcel ═══"
PIN=$(python3 "$SCRIPT_DIR/resolve_parcel.py" "$ADDRESS" "$PROJECT_DIR/run/tmp_resolve" 2>&1 | grep "^PIN:" | awk '{print $2}')

if [ -z "$PIN" ]; then
    echo "ERROR: Could not resolve address to a parcel number."
    rm -rf "$PROJECT_DIR/run/tmp_resolve"
    exit 1
fi

RUN_DIR="$PROJECT_DIR/run/$PIN"
mkdir -p "$RUN_DIR"
python3 "$SCRIPT_DIR/resolve_parcel.py" "$ADDRESS" "$RUN_DIR"
rm -rf "$PROJECT_DIR/run/tmp_resolve"

# Stage 1b: Fetch assessed values and characteristics
echo ""
echo "═══ Stage 1b: Fetching assessed values ═══"
python3 "$SCRIPT_DIR/fetch_account_value.py" "$PIN" "$RUN_DIR"

# Stage 3: Comparable sales
echo ""
echo "═══ Stage 3: Finding comparable sales ═══"
python3 "$SCRIPT_DIR/fetch_comps.py" "$RUN_DIR"

# Stage 4: Adjustment and valuation
echo ""
echo "═══ Stage 4: Adjusting comps ═══"
python3 "$SCRIPT_DIR/adjust_and_value.py" "$RUN_DIR"

# Stage 5: Case test
echo ""
echo "═══ Stage 5: Case test ═══"
python3 "$SCRIPT_DIR/case_test.py" "$RUN_DIR"

# Check go/no-go
GO=$(python3 -c "import json; print(json.load(open('$RUN_DIR/decision.json'))['go'])")

if [ "$GO" = "True" ]; then
    echo ""
    echo "═══ Stage 7: Building packet ═══"
    python3 "$SCRIPT_DIR/build_packet.py" "$RUN_DIR"
else
    echo ""
    echo "No over-assessment found. Packet not built."
fi

echo ""
echo "Run artifacts: $RUN_DIR/"
ls -1 "$RUN_DIR/"
