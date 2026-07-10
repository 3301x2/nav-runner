#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# List everything in the incoming buckets so we know exact filenames
# (case-sensitive) before trying to load.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

echo
echo "── testing-sandbox-123 (Rory's inbound) ──"
gcloud storage ls gs://testing-sandbox-123/ 2>&1 | sed 's/^/  /'

echo
echo "── incoming_vox (Vox files) ──"
gcloud storage ls gs://incoming_vox/ 2>&1 | sed 's/^/  /'

echo
echo "── Any other 'incoming' buckets in the sandbox project ──"
gcloud storage buckets list --project=fmn-sandbox --filter="name~incoming" \
    --format="value(name)" 2>&1 | sed 's/^/  /'
