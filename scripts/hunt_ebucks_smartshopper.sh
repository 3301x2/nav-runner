#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Hunt for the eBucks x SmartShopper LR question output.
#
# The clean-room Questions tab showed CRQ-200980 "eBucks x Pnp SmartSho..."
# but our sandbox mirror doesn't have it. This script looks in every place
# it could be hiding:
#   1. All GCS objects with 'ebucks' OR 'smart' in the path (case-insens)
#   2. All GCS buckets we can list (broader sweep for any bucket we missed)
#   3. Every PnP-adjacent dataset in prod for any table with 'ebucks' or
#      'smartshopper' in the name
#   4. Any file we can pdftotext under ~/pnp_deck_pages/ that mentions the
#      exact CRQ number
#
# Read-only. No writes anywhere.
#
# Usage:
#   bash scripts/hunt_ebucks_smartshopper.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    gcloud auth application-default login
fi

echo
echo "════════════════════════════════════════════════════════════"
echo "  Hunt for eBucks x SmartShopper LR question output"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Every GCS bucket you can see ──"
gcloud storage buckets list --format='value(name,location)' 2>/dev/null | head -50


echo
echo "── 2. Every object in gs://liveramp_output/ matching 'ebucks'/'smart' ──"
gcloud storage ls --recursive "gs://liveramp_output/**" 2>/dev/null \
    | grep -iE 'ebucks|smart|payday|burger|omnisient' | head -30


echo
echo "── 3. Every object in gs://picknpay_audience_uploads/ matching 'ebucks'/'smart' ──"
gcloud storage ls --recursive "gs://picknpay_audience_uploads/**" 2>/dev/null \
    | grep -iE 'ebucks|smart|payday' | head -30


echo
echo "── 4. All GCS buckets, search for any object mentioning ebucks/smart ──"
for b in $(gcloud storage buckets list --format='value(name)' 2>/dev/null); do
    hits=$(gcloud storage ls --recursive "gs://${b}/**" 2>/dev/null \
        | grep -iE 'ebucks|smartshopper|smart_shopper|payday_ebucks' \
        | head -5)
    if [ -n "$hits" ]; then
        echo
        echo "  gs://$b:"
        echo "$hits" | sed 's/^/    /'
    fi
done


echo
echo "── 5. Every table in prod PicknPay with ebucks/smart in the name ──"
bq query --quiet --use_legacy_sql=false --project_id=fmn-production-462014 \
    --location=africa-south1 --format=pretty --max_rows=30 \
    "SELECT table_name,
            (SELECT SUM(total_rows) FROM \`fmn-production-462014.PicknPay.INFORMATION_SCHEMA.PARTITIONS\` p WHERE p.table_name = t.table_name) AS rows
     FROM \`fmn-production-462014.PicknPay.INFORMATION_SCHEMA.TABLES\` t
     WHERE LOWER(table_name) LIKE '%ebucks%'
        OR LOWER(table_name) LIKE '%smart%'
        OR LOWER(table_name) LIKE '%payday%'
        OR LOWER(table_name) LIKE '%burger%'
     ORDER BY table_name"


echo
echo "── 6. Every prod dataset name mentioning ebucks/smart ──"
for proj in $(gcloud projects list --format='value(projectId)' \
    --filter='NOT projectId~^sys-' 2>/dev/null); do
    hits=$(bq --project_id="$proj" ls --datasets --max_results=200 2>/dev/null \
        | tail -n +3 | awk '{print $1}' \
        | grep -iE 'ebucks|smart|reward')
    if [ -n "$hits" ]; then
        echo
        echo "  Project: $proj"
        echo "$hits" | sed 's/^/    /'
    fi
done


echo
echo "── 7. Every PicknPay table's columns mentioning ebucks/smart ──"
bq query --quiet --use_legacy_sql=false --project_id=fmn-production-462014 \
    --location=africa-south1 --format=pretty --max_rows=30 \
    "SELECT table_name, column_name, data_type
     FROM \`fmn-production-462014.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
     WHERE LOWER(column_name) LIKE '%ebucks%'
        OR LOWER(column_name) LIKE '%smart%'
        OR LOWER(column_name) LIKE '%reward%'
        OR LOWER(column_name) LIKE '%loyalty%'
     ORDER BY table_name, column_name"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. If ANY of sections 4-6 lit up, we have more data."
echo "  If nothing found, we need to re-run the CRQ-200980 clean-room"
echo "  question OR request the output from PnP directly."
echo "════════════════════════════════════════════════════════════"
