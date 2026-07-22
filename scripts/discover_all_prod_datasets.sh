#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Full sweep of every dataset in fmn-production-462014 for anything we can
# use in the PnP unlock deck.
#
# We already know these prod datasets exist:
#   Adidas, ETL_DEV, Metropolitan, PicknPay, demographics_customer,
#   demographics_fld, demographics_mb, staging
#
# This script:
#   1. Lists every table in every dataset with row counts
#   2. Dumps the schema of any table that could carry FRG customer signal
#      (demographics, staging, PicknPay-adjacent) — enriches what we can
#      say about the FNB audiences on slide 12
#   3. Looks for anything with a rewards / loyalty / partner / campaign
#      column that could help us build eBucks-x-PnP proof stories
#   4. Confirms which of our sandbox mart tables we could stack on top
#      (mart_destination_benchmarks, mart_cluster_output, etc.)
#
# Read-only, metadata + tiny samples.
#
# Usage:
#   bash scripts/discover_all_prod_datasets.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    gcloud auth application-default login
fi

PROD="fmn-production-462014"
SB="fmn-sandbox"

bq_q_prod() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=50 "$1"
}
bq_q_sb() {
    bq query --quiet --use_legacy_sql=false --project_id="$SB" \
        --location=africa-south1 --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Full sweep of every dataset for the PnP unlock deck"
echo "════════════════════════════════════════════════════════════"


# ── 1. Every dataset in prod with a table count and total row count ────
echo
echo "── 1. Prod datasets, table count, total rows ──"
for ds in Adidas ETL_DEV Metropolitan PicknPay demographics_customer \
          demographics_fld demographics_mb staging; do
    tables=$(bq --project_id="$PROD" --location=africa-south1 \
        ls --max_results=200 "$PROD:$ds" 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
    echo "  $ds: $tables tables"
done


# ── 2. Table names in every dataset (compact) ──────────────────────────
echo
echo "── 2. Every table in every prod dataset ──"
for ds in Adidas ETL_DEV Metropolitan demographics_customer \
          demographics_fld demographics_mb; do
    echo
    echo "  ── $ds ──"
    bq_q_prod "
        SELECT
            table_name,
            (SELECT SUM(total_rows)
             FROM \`$PROD.$ds.INFORMATION_SCHEMA.PARTITIONS\` p
             WHERE p.table_name = t.table_name) AS rows
        FROM \`$PROD.$ds.INFORMATION_SCHEMA.TABLES\` t
        WHERE table_type = 'BASE TABLE'
        ORDER BY rows DESC NULLS LAST
        LIMIT 20
    " 2>&1 | head -30
done


# ── 3. Staging dataset (largest chance for customer signal) ────────────
echo
echo "── 3. Prod staging tables ──"
bq_q_prod "
    SELECT
        table_name,
        (SELECT SUM(total_rows)
         FROM \`$PROD.staging.INFORMATION_SCHEMA.PARTITIONS\` p
         WHERE p.table_name = t.table_name) AS rows,
        (SELECT COUNT(*) FROM \`$PROD.staging.INFORMATION_SCHEMA.COLUMNS\` c
         WHERE c.table_name = t.table_name) AS n_cols
    FROM \`$PROD.staging.INFORMATION_SCHEMA.TABLES\` t
    WHERE table_type = 'BASE TABLE'
    ORDER BY rows DESC NULLS LAST
    LIMIT 20
"


# ── 4. Any prod column mentioning reward / loyalty / partner / ebucks ──
echo
echo "── 4. Prod columns across all datasets mentioning reward/loyalty/ebucks/partner ──"
for ds in PicknPay staging demographics_customer demographics_mb; do
    hits=$(bq --project_id="$PROD" --location=africa-south1 \
        --format=csv --max_rows=50 query --quiet --use_legacy_sql=false \
        "SELECT CONCAT('$ds.', table_name, '.', column_name, ' (', data_type, ')') AS hit
         FROM \`$PROD.$ds.INFORMATION_SCHEMA.COLUMNS\`
         WHERE LOWER(column_name) LIKE '%reward%'
            OR LOWER(column_name) LIKE '%loyalty%'
            OR LOWER(column_name) LIKE '%ebucks%'
            OR LOWER(column_name) LIKE '%partner%'
            OR LOWER(column_name) LIKE '%smartshopper%'
            OR LOWER(column_name) LIKE '%smart_shopper%'" 2>/dev/null | tail -n +2)
    if [ -n "$hits" ]; then
        echo
        echo "  ── $ds ──"
        echo "$hits" | sed 's/^/    /'
    fi
done


# ── 5. Our sandbox marts: which of them cross-reference PnP? ────────────
echo
echo "── 5. Sandbox marts with PnP relevance ──"
bq_q_sb "
    SELECT
        table_name,
        (SELECT SUM(total_rows)
         FROM \`$SB.marts.INFORMATION_SCHEMA.PARTITIONS\` p
         WHERE p.table_name = t.table_name) AS rows
    FROM \`$SB.marts.INFORMATION_SCHEMA.TABLES\` t
    WHERE table_type = 'BASE TABLE'
    ORDER BY rows DESC NULLS LAST
    LIMIT 20
"


# ── 6. Sandbox analytics tables (the int_customer_category_spend surface) ─
echo
echo "── 6. Sandbox analytics tables ──"
bq_q_sb "
    SELECT
        table_name,
        (SELECT SUM(total_rows)
         FROM \`$SB.analytics.INFORMATION_SCHEMA.PARTITIONS\` p
         WHERE p.table_name = t.table_name) AS rows
    FROM \`$SB.analytics.INFORMATION_SCHEMA.TABLES\` t
    WHERE table_type = 'BASE TABLE'
    ORDER BY rows DESC NULLS LAST
    LIMIT 20
"


# ── 7. Sandbox spend_lookups + customer_spend (audience enrichment) ────
echo
echo "── 7. Sandbox spend_lookups + customer_spend + RM_Datasets ──"
for ds in spend_lookups customer_spend RM_Datasets; do
    echo
    echo "  ── $SB.$ds ──"
    bq_q_sb "
        SELECT table_name
        FROM \`$SB.$ds.INFORMATION_SCHEMA.TABLES\`
        WHERE table_type = 'BASE TABLE'
        ORDER BY table_name
        LIMIT 15
    " 2>&1 | head -20
done


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Screenshot and I'll fold what shows up into the deck."
echo "  Especially valuable: any hit in section 4 (loyalty/reward"
echo "  columns) means we can talk about eBucks-x-PnP without"
echo "  needing PnP to share anything new."
echo "════════════════════════════════════════════════════════════"
