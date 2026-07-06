#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Confirms the actual date window in stg_transactions before we build
# any pitch. Also spot-checks that the window is uniform across categories
# (no lookback bleed for a subset of merchants).
#
# Usage:
#   bash scripts/check_data_window.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)         PROJECT="fmn-sandbox" ;;
    production|prod|prd)    PROJECT="fmn-production" ;;
    *) echo "Usage: bash $0 [sandbox|production]"; exit 1 ;;
esac

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login --update-adc --quiet || exit 1
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty --max_rows=30 "$1" 2>/dev/null
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Data window check"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"

echo
echo "── 1. Overall date range (stg_transactions.EFF_DATE) ──"
bq_q "
    SELECT
        MIN(EFF_DATE)                                  AS first_date,
        MAX(EFF_DATE)                                  AS last_date,
        DATE_DIFF(MAX(EFF_DATE), MIN(EFF_DATE), DAY)   AS span_days,
        ROUND(DATE_DIFF(MAX(EFF_DATE), MIN(EFF_DATE), DAY) / 365.25, 2) AS span_years,
        COUNT(*)                                       AS total_rows
    FROM \`$PROJECT.staging.stg_transactions\`
"

echo
echo "── 2. Rows per month (see if the window is dense or has gaps) ──"
bq_q "
    SELECT
        FORMAT_DATE('%Y-%m', EFF_DATE) AS month,
        COUNT(*)                       AS row_count,
        COUNT(DISTINCT UNIQUE_ID)      AS customers,
        ROUND(SUM(trns_amt), 0)        AS spend
    FROM \`$PROJECT.staging.stg_transactions\`
    GROUP BY month
    ORDER BY month
"

echo
echo "── 3. Same check for Food Lovers specifically ──"
echo "(confirms Food Lovers window matches overall window — no bleed)"
bq_q "
    SELECT
        MIN(EFF_DATE)                                  AS first_date,
        MAX(EFF_DATE)                                  AS last_date,
        DATE_DIFF(MAX(EFF_DATE), MIN(EFF_DATE), DAY)   AS span_days,
        COUNT(*)                                       AS food_lovers_rows
    FROM \`$PROJECT.staging.stg_transactions\`
    WHERE UPPER(DESTINATION) LIKE '%FOOD LOVERS%'
"

echo
echo "── 4. Food Lovers rows per month ──"
bq_q "
    SELECT
        FORMAT_DATE('%Y-%m', EFF_DATE) AS month,
        COUNT(*)                       AS row_count,
        COUNT(DISTINCT UNIQUE_ID)      AS customers,
        ROUND(SUM(trns_amt), 0)        AS spend
    FROM \`$PROJECT.staging.stg_transactions\`
    WHERE UPPER(DESTINATION) LIKE '%FOOD LOVERS%'
    GROUP BY month
    ORDER BY month
"

echo
echo "── 5. Distinct DESTINATION values matching 'FOOD LOVERS' ──"
echo "(catches any spelling variants we should include or exclude)"
bq_q "
    SELECT
        DESTINATION,
        COUNT(*)                       AS row_count,
        COUNT(DISTINCT UNIQUE_ID)      AS customers,
        ROUND(SUM(trns_amt), 0)        AS spend
    FROM \`$PROJECT.staging.stg_transactions\`
    WHERE UPPER(DESTINATION) LIKE '%FOOD LOVERS%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
"

echo
echo "── 6. Groceries CATEGORY_TWO check ──"
echo "(so we know exactly what to use as the category filter)"
bq_q "
    SELECT
        CATEGORY_TWO,
        COUNT(*)                       AS row_count,
        COUNT(DISTINCT UNIQUE_ID)      AS customers,
        ROUND(SUM(trns_amt), 0)        AS spend
    FROM \`$PROJECT.staging.stg_transactions\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%GROCER%'
       OR UPPER(CATEGORY_TWO) LIKE '%SUPERMARKET%'
       OR UPPER(CATEGORY_TWO) LIKE '%FOOD%'
    GROUP BY CATEGORY_TWO
    ORDER BY spend DESC
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Read section 1 for the window, section 2 for month"
echo "  density, section 4 for Food Lovers month density, and"
echo "  section 6 for the exact CATEGORY_TWO to use."
echo "════════════════════════════════════════════════════════════"
