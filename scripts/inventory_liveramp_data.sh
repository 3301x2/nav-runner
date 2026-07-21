#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Full inventory of the LiveRamp data that's visible from our GCP identity.
#
# Discovered in discover_liveramp_gcp_connection.sh:
#   BQ:  fmn-production-462014.PicknPay (a whole dataset dedicated to PnP)
#   GCS: gs://liveramp_output/  (clean-room question results as CSVs)
#   GCS: gs://picknpay_audience_uploads/ (audiences we've pushed to PnP)
#
# This script goes deep:
#   1. Lists every table in fmn-production-462014.PicknPay with row counts
#   2. Dumps the schema of every table
#   3. Samples 5 rows from each table
#   4. Lists all dated partitions in gs://liveramp_output/
#   5. Lists all question runs inside each date partition
#   6. Downloads a preview (head) of the most recent CSVs into /tmp so we
#      can see what columns each clean-room question actually returns
#   7. Same treatment for gs://picknpay_audience_uploads/
#
# Read-only. Metadata + head-of-file reads. No writes, no mutations.
#
# Usage:
#   bash scripts/inventory_liveramp_data.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired, re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired, re-logging in..."
    gcloud auth application-default login
fi

PROD="fmn-production-462014"

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  LiveRamp full data inventory"
echo "  Project: $PROD"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Every table in fmn-production-462014.PicknPay ──"
echo "(row count + created timestamp per table)"
bq_q "
    SELECT
        table_name,
        row_count,
        ROUND(size_bytes / 1024 / 1024, 1)              AS size_mb,
        TIMESTAMP_MILLIS(creation_time)                 AS created_at,
        TIMESTAMP_MILLIS(last_modified_time)            AS last_modified
    FROM \`$PROD.PicknPay.__TABLES__\`
    ORDER BY last_modified_time DESC
    LIMIT 100
"


echo
echo "── 2. Schema of every table in PicknPay (column names + types) ──"
bq_q "
    SELECT
        table_name,
        column_name,
        data_type,
        ordinal_position
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    ORDER BY table_name, ordinal_position
    LIMIT 200
"


echo
echo "── 3. Sample rows from each table (top 5 tables by row count) ──"
top_tables=$(bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
    --location=africa-south1 --format=csv --max_rows=5 \
    "SELECT table_name FROM \`$PROD.PicknPay.__TABLES__\` ORDER BY row_count DESC LIMIT 5" \
    2>/dev/null | tail -n +2)

for t in $top_tables; do
    echo
    echo "  ── Sample from $PROD.PicknPay.$t ──"
    bq_q "SELECT * FROM \`$PROD.PicknPay.$t\` LIMIT 5"
done


echo
echo "── 4. All date partitions in gs://liveramp_output/ ──"
gcloud storage ls "gs://liveramp_output/" 2>/dev/null | sort -u


echo
echo "── 5. Question runs inside the 3 most-recent date partitions ──"
latest_dates=$(gcloud storage ls "gs://liveramp_output/" 2>/dev/null \
    | grep -oE 'date=[0-9-]+' | sort -u | tail -3)

for d in $latest_dates; do
    echo
    echo "  ── gs://liveramp_output/$d/ ──"
    gcloud storage ls "gs://liveramp_output/$d/" 2>/dev/null | head -20
done


echo
echo "── 6. Every unique CSV filename pattern in gs://liveramp_output/ ──"
echo "(gives us the naming convention: question-name + date + timestamp)"
gcloud storage ls --recursive "gs://liveramp_output/**" 2>/dev/null \
    | grep -Ei '\.csv$|\.parquet$' \
    | sed -E 's|.*/data/||; s|_2026-[0-9-]+_[0-9-]+\.csv$|_YYYY-MM-DD_HH-MM-SS.csv|; s|.*/||' \
    | sort -u | head -50


echo
echo "── 7. Sample: head of the 3 most recent CSV outputs ──"
echo "(so we know what columns each clean-room question returns)"
latest_csvs=$(gcloud storage ls --recursive "gs://liveramp_output/**" 2>/dev/null \
    | grep -Ei '\.csv$' | tail -3)

mkdir -p /tmp/lr_sample
for uri in $latest_csvs; do
    fname=$(basename "$uri")
    echo
    echo "  ── $uri ──"
    gcloud storage cp "$uri" "/tmp/lr_sample/$fname" 2>/dev/null
    if [ -f "/tmp/lr_sample/$fname" ]; then
        echo "    File size: $(ls -lh "/tmp/lr_sample/$fname" | awk '{print $5}')"
        echo "    First 3 lines:"
        head -3 "/tmp/lr_sample/$fname" | sed 's/^/      /'
        echo "    Row count:"
        wc -l "/tmp/lr_sample/$fname" | awk '{print "      " $1 " rows"}'
    fi
done


echo
echo "── 8. gs://picknpay_audience_uploads/ full listing ──"
gcloud storage ls --recursive "gs://picknpay_audience_uploads/**" 2>/dev/null | head -40


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Read:"
echo "  Section 1: what PnP tables live in our prod BQ"
echo "  Section 2: their schemas (column names decide what joins are possible)"
echo "  Section 3: what the data actually looks like"
echo "  Sections 4-7: what LiveRamp clean-room question outputs we have"
echo "  Section 8: what audiences we've pushed to PnP"
echo "════════════════════════════════════════════════════════════"
