#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Check whether we can derive NTB (account tenure ≤ 3 months) from
# columns we already have, before going back to Charmain.
#
# Looks at:
#   1. profile_age (demo_3) — most promising candidate
#   2. All other potentially-tenure-shaped columns in stg_customers
#   3. Full schema of customer_spend.base_data — anything we missed?
#   4. Transaction-derived first-seen date per customer (proxy only)
#
# Usage:
#   bash scripts/discover_tenure_columns.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)         PROJECT="fmn-sandbox" ;;
    production|prod|prd)    PROJECT="fmn-production-462014" ;;
    *) echo "Usage: bash $0 [sandbox|production]"; exit 1 ;;
esac

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired — re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired — re-logging in..."
    gcloud auth application-default login
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Tenure column discovery — can we derive NTB without Charmain?"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"

echo
echo "── 1. profile_age (demo_3) — distinct values + counts ──"
echo "If this looks like months (0, 1, 2, ... 24+) → we have NTB"
echo "If it's a bucket code or years → it's something else"
bq_q "
    SELECT profile_age, COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\`
    GROUP BY profile_age
    ORDER BY profile_age
    LIMIT 50
"

echo
echo "── 2. profile_age — summary stats (helps tell months vs years) ──"
bq_q "
    SELECT
        MIN(SAFE_CAST(profile_age AS FLOAT64))                              AS min_val,
        MAX(SAFE_CAST(profile_age AS FLOAT64))                              AS max_val,
        ROUND(AVG(SAFE_CAST(profile_age AS FLOAT64)), 2)                    AS avg_val,
        APPROX_QUANTILES(SAFE_CAST(profile_age AS FLOAT64), 4)[OFFSET(2)]   AS median_val,
        COUNTIF(profile_age IS NULL)                                        AS null_count,
        COUNT(*)                                                            AS total
    FROM \`$PROJECT.staging.stg_customers\`
"

echo
echo "── 3. Other potentially-tenure-shaped columns (sample values) ──"
echo "vertical_sales_index, main_banked, credit_risk_class — quick re-check"
bq_q "
    SELECT 'vertical_sales_index' AS column_name, CAST(vertical_sales_index AS STRING) AS value, COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\` GROUP BY value ORDER BY customers DESC LIMIT 10
"

echo
echo "── 4. FULL schema of customer_spend.base_data ──"
echo "If there's any column with 'tenure', 'open', 'age', 'months', 'date'"
echo "in the name that we didn't surface into staging, it shows up here."
bq_q "
    SELECT column_name, data_type
    FROM \`$PROJECT.customer_spend.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'base_data'
    ORDER BY ordinal_position
"

echo
echo "── 5. FALLBACK proxy — first-seen date per customer (from transactions) ──"
echo "If profile_age doesn't work, this is the only proxy we have."
echo "(Note: this is tenure IN OUR DATASET, not tenure at FNB.)"
bq_q "
    WITH first_seen AS (
        SELECT
            UNIQUE_ID,
            MIN(EFF_DATE) AS first_txn_date,
            MAX(EFF_DATE) AS last_txn_date,
            DATE_DIFF(MAX(EFF_DATE), MIN(EFF_DATE), MONTH) AS tenure_months
        FROM \`$PROJECT.staging.stg_transactions\`
        GROUP BY UNIQUE_ID
    )
    SELECT
        CASE
            WHEN tenure_months <= 3  THEN 'a. 0-3m (NTP proxy)'
            WHEN tenure_months <= 6  THEN 'b. 3-6m (RTP proxy)'
            ELSE                          'c. 6m+   (ETP proxy)'
        END                                                AS tenure_bucket,
        COUNT(*)                                           AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM first_seen
    GROUP BY tenure_bucket
    ORDER BY tenure_bucket
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Send Sections 1, 2, and 4 to chat —"
echo "  that's enough to tell whether profile_age = tenure"
echo "  and whether base_data has a column we missed."
echo "════════════════════════════════════════════════════════════"
