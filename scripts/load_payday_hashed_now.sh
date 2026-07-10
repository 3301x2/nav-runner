#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# The new payday_pnp_hashed file was delivered as a local download (not via
# bucket) because they had upload permission issues.
#
# This script:
#   1. Uploads the local file to the sandbox bucket
#   2. Runs the standard sandbox load + prod promote flow
#
# Local source: ~/Downloads/payday_pnp_hashed_20260710.csv (~724 MB)
# GCS target:   gs://testing-sandbox-123/payday_pnp_hashed_20260710.csv
# Sandbox tbl:  fmn-sandbox.staging.payday_pnp_hashed_meta_audience
# Prod tbl:     fmn-production-462014.staging.payday_pnp_hashed_meta_audience
#
# Usage:
#   bash scripts/load_payday_hashed_now.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

LOCAL_FILE="$HOME/Downloads/payday_pnp_hashed_20260710.csv"
BUCKET="testing-sandbox-123"
OBJECT="payday_pnp_hashed_20260710.csv"
GCS_URI="gs://$BUCKET/$OBJECT"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Payday-hashed load — Nicol's regenerated file"
echo "════════════════════════════════════════════════════════════"
echo "  Local:   $LOCAL_FILE"
echo "  GCS:     $GCS_URI"
echo "════════════════════════════════════════════════════════════"


# ── 1. Confirm the local file exists ────────────────────────────────
if [ ! -f "$LOCAL_FILE" ]; then
    echo
    echo "✗ File not found at $LOCAL_FILE"
    echo "  Check ~/Downloads/ for the file and adjust the path in this script."
    exit 1
fi

SIZE_MB=$(du -m "$LOCAL_FILE" | cut -f1)
echo
echo "── 1. Local file found ──"
echo "   Size: ${SIZE_MB} MB"


# ── 2. Peek at the header first (before uploading) ──────────────────
echo
echo "── 2. Header line (column names) ──"
HEADER=$(head -1 "$LOCAL_FILE")
echo "   $HEADER"
COL_COUNT=$(echo "$HEADER" | awk -F',' '{print NF}')
echo "   Total columns: $COL_COUNT"

echo
echo "── 3. Look for identifier-shaped columns ──"
echo "$HEADER" | tr ',' '\n' | grep -iE 'id|passport|saidnr|cif|national|uid|hash' \
    | sed 's/^/   🎯 /' || echo "   (no obvious ID-shaped column names found)"


# ── 4. Upload to bucket ──────────────────────────────────────────────
echo
echo "── 4. Uploading to $GCS_URI (${SIZE_MB} MB — takes ~1-2 min) ──"
if gcloud storage cp "$LOCAL_FILE" "$GCS_URI"; then
    echo "   ✓ Upload complete"
else
    echo "   ✗ Upload failed"
    exit 1
fi


# ── 5. Run the standard load-and-promote via the FB audience loader ─
echo
echo "── 5. Running sandbox load + prod promote ──"
exec bash "$SCRIPT_DIR/load_fb_audience_all.sh" \
    --source "$GCS_URI"
