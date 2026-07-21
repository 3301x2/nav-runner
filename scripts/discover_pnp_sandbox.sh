#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Discovery queries. Reads PicknPay tables from prod directly (they already
# exist there, no reason to duplicate) and LR clean-room mirrors from
# sandbox (loaded by ingest_liveramp_to_sandbox.sh).
#
# One-screen-friendly output so screenshots stay readable.
#
# Sections:
#   1. What tables exist in PROD.PicknPay (rows + size + last modified)
#   2. What tables exist in SANDBOX.pnp_liveramp (the LR mirrors)
#   3. Schema of the three most important PicknPay tables
#   4. Categorical dimension distributions (Retail_Model, MBD_Tier,
#      Hypersegment, KPI_Risk_Class) from Audience_Upload
#   5. PnP spend headline: customers, visits, spend, wallet share
#   6. Row counts of every LR output table
#
# Read-only. No writes.
#
# Usage:
#   bash scripts/discover_pnp_sandbox.sh
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
SB="fmn-sandbox"
DS="pnp_liveramp"

# We run the query in the project that OWNS the target table, so bq bills
# and locates it correctly. Both projects share africa-south1.
bq_prod() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=50 "$1"
}
bq_sb() {
    bq query --quiet --use_legacy_sql=false --project_id="$SB" \
        --location=africa-south1 --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  PnP + LiveRamp discovery"
echo "  PicknPay tables: $PROD.PicknPay (queried in place)"
echo "  LR mirrors:      $SB.$DS (ingested from GCS)"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. PROD.PicknPay tables (rows + size) ──"
bq_prod "
    SELECT
        t.table_name,
        p.total_rows,
        ROUND(p.total_logical_bytes / 1024 / 1024, 1) AS size_mb,
        DATE(t.last_modified_time) AS last_modified
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name,
               SUM(total_rows) AS total_rows,
               SUM(total_logical_bytes) AS total_logical_bytes
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE t.table_type = 'BASE TABLE'
    ORDER BY p.total_rows DESC NULLS LAST
    LIMIT 30
"


echo
echo "── 2. SANDBOX.$DS tables (LR mirrors from GCS) ──"
bq_sb "
    SELECT
        t.table_name,
        p.total_rows,
        ROUND(p.total_logical_bytes / 1024 / 1024, 1) AS size_mb,
        DATE(t.last_modified_time) AS last_modified
    FROM \`$SB.$DS.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name,
               SUM(total_rows) AS total_rows,
               SUM(total_logical_bytes) AS total_logical_bytes
        FROM \`$SB.$DS.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE t.table_type = 'BASE TABLE'
    ORDER BY p.total_rows DESC NULLS LAST
    LIMIT 30
"


echo
echo "── 3. Schema of the three flagship PicknPay tables ──"
bq_prod "
    SELECT table_name, column_name, data_type, ordinal_position
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name IN (
        'Audience_Upload_20260206',
        'latest_fnb_trns_base',
        'pnp_clothing_extract_20260317'
    )
    ORDER BY table_name, ordinal_position
    LIMIT 100
"


echo
echo "── 4a. Retail_Model distribution (Audience_Upload_20260206) ──"
bq_prod "
    SELECT Retail_Model,
        COUNT(*) AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
    GROUP BY Retail_Model
    ORDER BY customers DESC
    LIMIT 20
"

echo
echo "── 4b. MBD_Tier distribution ──"
bq_prod "
    SELECT MBD_Tier,
        COUNT(*) AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
    GROUP BY MBD_Tier
    ORDER BY customers DESC
    LIMIT 15
"

echo
echo "── 4c. Hypersegment distribution ──"
bq_prod "
    SELECT Hypersegment,
        COUNT(*) AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
    GROUP BY Hypersegment
    ORDER BY customers DESC
    LIMIT 15
"

echo
echo "── 4d. KPI_Risk_Class distribution ──"
bq_prod "
    SELECT KPI_Risk_Class,
        COUNT(*) AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
    GROUP BY KPI_Risk_Class
    ORDER BY customers DESC
    LIMIT 15
"


echo
echo "── 5. PnP spend headline ──"
bq_prod "
    SELECT
        COUNT(*)                       AS total_customers,
        COUNTIF(nr_pnp_trns > 0)       AS pnp_active_customers,
        ROUND(AVG(nr_pnp_trns), 1)     AS avg_pnp_visits,
        ROUND(AVG(val_pnp_trns), 0)    AS avg_pnp_spend,
        ROUND(SUM(val_pnp_trns), 0)    AS total_pnp_spend,
        ROUND(AVG(val_tot_trns), 0)    AS avg_total_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_pnp_wallet_share_pct
    FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
    WHERE val_tot_trns > 0
"


echo
echo "── 6. Every lr_out_* / aud_* table row count (sandbox) ──"
bq_sb "
    SELECT t.table_name, p.total_rows
    FROM \`$SB.$DS.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name, SUM(total_rows) AS total_rows
        FROM \`$SB.$DS.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE table_name LIKE 'lr_out_%' OR table_name LIKE 'aud_%'
    ORDER BY p.total_rows DESC NULLS LAST
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Screenshot the sections you want and I'll design the"
echo "  Tuesday deck slides + next queries from what shows up."
echo "════════════════════════════════════════════════════════════"
