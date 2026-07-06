#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Food Lovers investigation — ground-truth every KPI Simphiwe put on the
# slide, so we can hand him a clean corrected version.
#
# Explicitly labels scope on every number (Food Lovers vs Groceries vs
# FNB-wide) so bleed-through is visible.
#
# Uses marts (mart_destination_benchmarks + int_customer_category_spend)
# as source of truth. NEVER sums directly from stg_transactions (fanout
# from lookup joins inflates spend by ~5000x).
#
# Usage:
#   bash scripts/investigate_food_lovers.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)         PROJECT="fmn-sandbox" ;;
    production|prod|prd)    PROJECT="fmn-production-462814" ;;
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
echo "  FOOD LOVERS INVESTIGATION"
echo "  Project: $PROJECT"
echo "  Window:  rolling 12 months (as materialised in marts)"
echo "════════════════════════════════════════════════════════════"


echo
echo "══════════════ SCOPE 1: FNB-wide totals ═══════════════════"

echo
echo "── 1a. Total FNB customers (whole base) ──"
bq_q "
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS fnb_customers
    FROM \`$PROJECT.staging.stg_customers\`
"

echo
echo "── 1b. Total FNB customers that shopped in the 12mo window ──"
bq_q "
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS active_customers,
        ROUND(SUM(dest_spend), 0) AS total_spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
"


echo
echo "══════════════ SCOPE 2: Groceries category ════════════════"

echo
echo "── 2a. Groceries totals (from int_customer_category_spend — clean) ──"
bq_q "
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS groceries_customers,
        ROUND(SUM(dest_spend), 0) AS groceries_spend,
        SUM(dest_txn_count)       AS groceries_transactions
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE CATEGORY_TWO = 'Groceries'
"

echo
echo "── 2b. Groceries top 10 destinations by spend (competitive set) ──"
bq_q "
    SELECT
        DESTINATION,
        customers,
        transactions,
        total_spend,
        avg_txn_value,
        spend_per_customer,
        market_share_pct,
        penetration_pct,
        spend_rank
    FROM \`$PROJECT.marts.mart_destination_benchmarks\`
    WHERE CATEGORY_TWO = 'Groceries'
    ORDER BY total_spend DESC
    LIMIT 10
"


echo
echo "══════════════ SCOPE 3: Food Lovers ═══════════════════════"

echo
echo "── 3a. Both DESTINATIONs (Food Lovers Market + Eatery) — separate ──"
bq_q "
    SELECT
        DESTINATION,
        customers,
        transactions,
        total_spend,
        avg_txn_value,
        spend_per_customer,
        market_share_pct,
        penetration_pct,
        avg_share_of_wallet,
        spend_rank
    FROM \`$PROJECT.marts.mart_destination_benchmarks\`
    WHERE CATEGORY_TWO = 'Groceries'
      AND UPPER(DESTINATION) LIKE '%FOOD LOVERS%'
    ORDER BY total_spend DESC
"

echo
echo "── 3b. Both DESTINATIONs COMBINED (union of customer base) ──"
echo "IMPORTANT: NO CATEGORY_TWO filter — Eatery may live in a different"
echo "category (Fast Food/Restaurants) than Market (Groceries). Filtering"
echo "on Groceries alone would silently drop the Eatery from the combined"
echo "total."
bq_q "
    SELECT
        'Food Lovers (Market + Eatery combined)' AS scope,
        COUNT(DISTINCT UNIQUE_ID)                AS customers,
        SUM(dest_txn_count)                      AS transactions,
        ROUND(SUM(dest_spend), 0)                AS total_spend,
        ROUND(SUM(dest_spend) / NULLIF(COUNT(DISTINCT UNIQUE_ID), 0), 0)
                                                 AS spend_per_customer,
        ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2)
                                                 AS avg_txn_value
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
"

echo
echo "── 3c. Overlap: customers with BOTH Market AND Eatery ──"
bq_q "
    WITH market AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) = 'FOOD LOVERS MARKET'
    ),
    eatery AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) = 'FOOD LOVERS EATERY'
    )
    SELECT
        (SELECT COUNT(*) FROM market)                              AS market_only_or_both,
        (SELECT COUNT(*) FROM eatery)                              AS eatery_only_or_both,
        (SELECT COUNT(*) FROM market m JOIN eatery e USING (UNIQUE_ID))
                                                                   AS in_both,
        (SELECT COUNT(*) FROM (
            SELECT UNIQUE_ID FROM market
            UNION DISTINCT
            SELECT UNIQUE_ID FROM eatery))                         AS combined_unique
"


echo
echo "══════════════ SCOPE 4: Sanity checks ═════════════════════"

echo
echo "── 4a. Food Lovers % of Groceries (using combined) ──"
bq_q "
    WITH fl AS (
        SELECT
            COUNT(DISTINCT UNIQUE_ID) AS customers,
            ROUND(SUM(dest_spend), 0) AS spend,
            SUM(dest_txn_count)       AS transactions
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    ),
    grp AS (
        SELECT
            COUNT(DISTINCT UNIQUE_ID) AS customers,
            ROUND(SUM(dest_spend), 0) AS spend,
            SUM(dest_txn_count)       AS transactions
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE CATEGORY_TWO = 'Groceries'
    )
    SELECT
        ROUND(100.0 * fl.customers / grp.customers, 2) AS fl_pct_of_groc_customers,
        ROUND(100.0 * fl.spend     / grp.spend,     2) AS fl_pct_of_groc_spend,
        ROUND(100.0 * fl.transactions / grp.transactions, 2) AS fl_pct_of_groc_transactions
    FROM fl CROSS JOIN grp
"

echo
echo "── 4b. Demographics of Food Lovers combined audience ──"
bq_q "
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        COUNT(*)                                                            AS customers,
        ROUND(AVG(c.age), 1)                                                AS avg_age,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Male'   THEN c.UNIQUE_ID END) AS male,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Female' THEN c.UNIQUE_ID END) AS female,
        COUNT(DISTINCT CASE WHEN c.gender_label = 'Unknown' THEN c.UNIQUE_ID END) AS gender_unknown
    FROM fl_custs f
    JOIN \`$PROJECT.staging.stg_customers\` c USING (UNIQUE_ID)
"


echo
echo "══════════════ SCOPE 5: ML segment scope check ════════════"
echo "(the 'client-specific vs total-base' caveat you flagged)"
echo
echo "── 5a. Food Lovers customers segmented by their FNB-wide cluster ──"
echo "Note: mart_cluster_output labels are based on WHOLE FNB spend,"
echo "not Food Lovers spend. A 'Champion' here spends big across all"
echo "FNB — most of that spend may not be at Food Lovers."
bq_q "
    WITH fl_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) IN ('FOOD LOVERS MARKET', 'FOOD LOVERS EATERY')
    )
    SELECT
        co.segment_name,
        COUNT(*)                                              AS fl_customers_in_segment,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)    AS pct_of_fl_customers
    FROM fl_custs f
    JOIN \`$PROJECT.marts.mart_cluster_output\` co USING (UNIQUE_ID)
    GROUP BY co.segment_name
    ORDER BY fl_customers_in_segment DESC
"


echo
echo "══════════════ Compare vs Simphiwe's slide numbers ════════"
echo
echo "  Simphiwe's slide 1 said:"
echo "    • 5.76m FRG Retail Customers        (expected: FNB-wide from 1a)"
echo "    • 5.09m Groceries Customers         (expected: 2a groceries_customers)"
echo "    • 111,076,254 Transactions          (expected: NEITHER — bleed check)"
echo "    • TOTAL Spend R4,540,401,245        (expected: matches 3b combined?)"
echo "    • 1,083,467 Number of shoppers      (expected: 3a Food Lovers MARKET only?)"
echo "    • R426.39 Avg transaction value     (expected: matches 3a Market avg_txn_value)"
echo "    • 46 Avg age of Food Lovers customer (expected: 4b avg_age)"
echo "    • R4,579,532,006 Value of Transactions (expected: matches R4.54B ± small delta)"
echo
echo "  Compare row-by-row using the outputs above."
echo "════════════════════════════════════════════════════════════"
