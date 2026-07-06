#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Team expects 1.5M+ rows in the Aspire file — we loaded 15,407.
# Is the file itself short (uploader mistake) or did we skip rows (our
# mistake)?
#
# Checks:
#   1. File size on GCS (a 1.5M-row hashed CSV should be ~600 MB — 671 KB
#      is only enough for ~15k rows, so file size alone probably answers it)
#   2. Byte size on the object
#   3. Row count in the raw CSV (wc -l via streaming cat)
#   4. Row count in BQ (COUNTIF the file has more than we loaded, we
#      skipped rows silently)
#   5. Load-job errors (`bq show -j` for the last load — shows total input
#      rows, rows written, rows skipped)
#
# Usage:
#   bash scripts/diagnose_aspire_row_count.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROJECT="fmn-sandbox"
BUCKET="testing-sandbox-123"
OBJECT="ASPIRE_PRIMELIFE_20260706_FB.csv"
URI="gs://$BUCKET/$OBJECT"
TABLE_SQL="fmn-sandbox.staging.aspire_primelife_meta_audience"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Aspire row-count reconciliation"
echo "════════════════════════════════════════════════════════════"
echo
echo "  Expected by team:  1,500,000+  rows"
echo "  Loaded to BQ:      15,407      rows"
echo "  Delta:             ~100x short"
echo


# ── 1. File size on GCS ─────────────────────────────────────────────
echo "── 1. Object size on GCS ──"
gcloud storage objects describe "$URI" \
    --format="value(size)" 2>/dev/null | \
    awk '{
        bytes = $1;
        mb    = bytes / 1024 / 1024;
        gb    = mb / 1024;
        printf "   Bytes: %s (%.2f MB / %.3f GB)\n", $1, mb, gb;
        printf "   Rough estimate: hashed audience row ≈ 400-500 bytes → this file could hold ~%d rows\n", bytes / 450;
    }'


# ── 2. Full byte size + last-modified ────────────────────────────────
echo
echo "── 2. Full object metadata ──"
gcloud storage objects describe "$URI" 2>/dev/null | \
    grep -E "^(size|updated|content_type|crc32c|md5_hash|generation):" | \
    head -8


# ── 3. Actual row count in the CSV ───────────────────────────────────
echo
echo "── 3. Raw row count in the CSV (streaming wc -l) ──"
echo "   (may take a moment for large files)"
ROW_COUNT=$(gcloud storage cat "$URI" 2>/dev/null | wc -l | tr -d ' ')
echo "   Rows in file (incl header): $ROW_COUNT"
DATA_ROWS=$((ROW_COUNT - 1))
echo "   Data rows (excl header):    $DATA_ROWS"


# ── 4. BQ table row count ────────────────────────────────────────────
echo
echo "── 4. Row count in BQ table ──"
bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty \
    "SELECT COUNT(*) AS bq_row_count FROM \`$TABLE_SQL\`"


# ── 5. Verdict ───────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════"
echo "  Verdict"
echo "════════════════════════════════════════════════════════════"
if [ "$DATA_ROWS" -lt 100000 ]; then
    echo
    echo "  🚩 THE FILE ONLY HAS $DATA_ROWS DATA ROWS — this is an"
    echo "     UPLOADER MISTAKE, not ours."
    echo
    echo "  Send back to whoever generated the CSV — the file itself is"
    echo "  ~100x smaller than expected."
elif [ "$DATA_ROWS" -gt 1000000 ]; then
    echo
    echo "  🚩 THE FILE HAS $DATA_ROWS DATA ROWS but only 15,407 loaded."
    echo "     OUR LOAD DROPPED ROWS SILENTLY."
    echo
    echo "  Fix: rerun the load, watching --max_bad_records + inspect"
    echo "  bq show -j <job_id> for the exact skipped counts."
else
    echo
    echo "  🤔 File has $DATA_ROWS rows — bigger than what we loaded"
    echo "     but not the 1.5M expected. Something else going on."
fi
echo
echo "════════════════════════════════════════════════════════════"
