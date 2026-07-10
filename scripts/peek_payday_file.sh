#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Peek at the existing payday_pnp_InclusionA CSV to see if it already has
# an ID column. If it does, we may not need Nicol to regenerate.
#
# Shows:
#   1. Exact filename (from list_incoming_files output)
#   2. Header line (column names)
#   3. First 3 data rows
#   4. Column count
#   5. Approximate row count (line count of streamed file)
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

BUCKET="testing-sandbox-123"
NAME_PATTERN="payday_pnp_Inclusion"

echo
echo "── 1. Files matching pattern in gs://$BUCKET/ ──"
gcloud storage ls "gs://$BUCKET/" 2>&1 | grep -i "$NAME_PATTERN" | sed 's/^/  /'

# Take the first match
URI=$(gcloud storage ls "gs://$BUCKET/" 2>&1 | grep -i "$NAME_PATTERN" | head -1)

if [ -z "$URI" ]; then
    echo
    echo "No matching file found. Check bucket contents:"
    bash "$(cd "$(dirname "$0")" && pwd)/list_incoming_files.sh"
    exit 1
fi

echo
echo "── 2. Header line (column names) ──"
HEADER=$(gcloud storage cat "$URI" 2>/dev/null | head -1)
echo "$HEADER" | sed 's/^/  /'
echo
COL_COUNT=$(echo "$HEADER" | awk -F',' '{print NF}')
echo "  Total columns: $COL_COUNT"


echo
echo "── 3. First 3 data rows (redacted preview) ──"
gcloud storage cat "$URI" 2>/dev/null | head -4 | tail -3 | \
    awk -F',' '{
        for (i=1; i<=NF; i++) {
            val = $i
            if (length(val) > 12) val = substr(val, 1, 6) "..." substr(val, length(val)-3)
            printf "  Col%d: %s\n", i, val
        }
        print "  ---"
    }'


echo
echo "── 4. Column names indexed (for quick reference) ──"
echo "$HEADER" | awk -F',' '{
    for (i=1; i<=NF; i++) {
        printf "  Col %2d: %s\n", i, $i
    }
}'


echo
echo "── 5. Look for identifier-shaped columns ──"
echo "$HEADER" | tr ',' '\n' | grep -iE 'id|passport|saidnr|cif|national|uid|hash' | sed 's/^/  🎯 /' || \
    echo "  (no obvious ID-shaped column names found)"


echo
echo "── 6. Approx row count (streaming — takes ~30s for 1.5GB) ──"
LINE_COUNT=$(gcloud storage cat "$URI" 2>/dev/null | wc -l | tr -d ' ')
echo "  Rows in file (incl header): $LINE_COUNT"
if [ -n "$LINE_COUNT" ] && [ "$LINE_COUNT" -gt 0 ]; then
    DATA_ROWS=$((LINE_COUNT - 1))
    echo "  Data rows (excl header):    $DATA_ROWS"
fi


echo
echo "════════════════════════════════════════════════════════════"
echo "  What to do next"
echo "════════════════════════════════════════════════════════════"
echo "  If you saw an ID / passport / national / SAIDNR column above,"
echo "  the file may already have what Nicol was going to add."
echo "  Screenshot the output back to Prosper before running any load."
echo "════════════════════════════════════════════════════════════"
