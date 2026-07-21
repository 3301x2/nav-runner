#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Push the LiveRamp inventory files to the repo so Prosper's assistant can
# read them directly (no more screenshot ping-pong).
#
# Run AFTER inventory_liveramp_data.sh has completed.
#
# What gets committed (safe):
#   lr_inventory/00_tables.txt         PicknPay tables + row counts
#   lr_inventory/01_schemas.txt        every column of every table
#   lr_inventory/02_samples/*.txt      5 sample rows per top-5 table (already
#                                       redacted to pretty-print output)
#   lr_inventory/03_lr_partitions.txt  LR output date folders
#   lr_inventory/04_lr_all_files.txt   every LR output file path
#   lr_inventory/05_lr_file_types.txt  unique LR question filename patterns
#   lr_inventory/06_lr_previews/*.preview.txt  first 5 lines + row count only
#   lr_inventory/07_audience_uploads.txt  audience-upload bucket contents
#   lr_inventory/08_summary.txt        one-page overview
#
# What's blocked by .gitignore (unsafe to publish):
#   lr_inventory/06_lr_previews/*.csv (raw hashed CSVs)
#   lr_inventory/06_lr_previews/*.parquet
#   lr_inventory/02_samples/*.csv
#
# Usage:
#   bash scripts/push_lr_inventory.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

cd "$(dirname "$0")/.." || exit 1

if [ ! -d lr_inventory ]; then
    echo "❌ lr_inventory/ does not exist yet."
    echo "   Run this first:"
    echo "     bash scripts/inventory_liveramp_data.sh"
    exit 1
fi

echo
echo "── What will be committed ──"
git add lr_inventory/
git status --short lr_inventory/ | head -40

echo
echo "── What is blocked by .gitignore (should be raw data files only) ──"
git status --ignored --short lr_inventory/ 2>/dev/null | grep '!!' | head -20 \
    || echo "  (none)"

echo
read -rp "Proceed with commit + push? [y/N] " confirm
if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
    echo "Aborted. Nothing committed."
    exit 0
fi

git commit -m "add LR inventory: PicknPay dataset schemas + LR clean-room output listings + summary" \
    && git push 2>&1 | tail -5

echo
echo "✓ Pushed. Prosper's assistant can now read lr_inventory/*.txt directly."
