#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Engen + Woolworths partnership discovery.
#
# Engen has Woolies Foodstop concessions inside some of their filling
# stations. Pierre wants a pitch that shows how the two businesses can
# extract value from that partnership, using the FNB card view.
#
# The pitch hinges on THREE cohorts:
#   1. Engen-only shoppers (fuel & forecourt buyers who don't visit Woolies)
#   2. Woolworths-only shoppers (grocery/apparel buyers who don't visit Engen)
#   3. THE SHARED COHORT: customers active at BOTH (already living the
#      partnership; the case study for growth)
#
# Sections:
#   1. Engen DESTINATION variants (all Engen banners in the data)
#   2. Woolworths DESTINATION variants (Food vs main vs FoodStop, etc.)
#   3. Fuel/forecourt competitive set (Engen's rivals: Shell, BP, Sasol,
#      Total, Astron, Puma) so we can position Engen inside its category
#   4. Premium grocery competitive set (Woolworths' rivals: Checkers,
#      Pick n Pay, Spar) so we can position Woolies inside its category
#   5. THE SHARED COHORT: customers who spend at both Engen AND Woolies
#      (with spend, avg basket, cross-shop overlap)
#   6. Woolworths FoodStop / Food destinations at forecourts (if any
#      distinct DESTINATION exists in the data)
#   7. Category coverage (what CATEGORY_TWO values Engen sits in)
#
# Usage:
#   bash scripts/discover_engen_woolies.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)      PROJECT="fmn-sandbox"           ;;
    production|prod|prd) PROJECT="fmn-production-462014" ;;
    *) echo "Usage: bash $0 [sandbox|production]"; exit 1 ;;
esac

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired, re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired, re-logging in..."
    gcloud auth application-default login
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Engen + Woolworths partnership discovery"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Engen DESTINATION variants ──"
echo "Catches ENGEN, ENGEN 1STOP, ENGEN QUICKSHOP, etc."
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%ENGEN%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 2. Woolworths DESTINATION variants ──"
echo "Catches WOOLWORTHS, WOOLWORTHS FOOD, WOOLIES, W CAFE, FOODSTOP, etc."
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%WOOLWORTH%'
       OR UPPER(DESTINATION) LIKE '%WOOLIES%'
       OR UPPER(DESTINATION) LIKE '%FOODSTOP%'
       OR UPPER(DESTINATION) LIKE '%W CAFE%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 3. Fuel/forecourt competitive set (Engen's category) ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%SHELL%'
       OR UPPER(DESTINATION) LIKE '%BP %' OR UPPER(DESTINATION) = 'BP'
       OR UPPER(DESTINATION) LIKE '%SASOL%'
       OR UPPER(DESTINATION) LIKE '%TOTAL %' OR UPPER(DESTINATION) = 'TOTAL'
       OR UPPER(DESTINATION) LIKE '%TOTALENERGIES%'
       OR UPPER(DESTINATION) LIKE '%ASTRON%'
       OR UPPER(DESTINATION) LIKE '%PUMA%'
       OR UPPER(DESTINATION) LIKE '%CALTEX%'
       OR UPPER(DESTINATION) LIKE '%ENGEN%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY spend DESC
    LIMIT 25
"


echo
echo "── 4. Premium grocery competitive set (Woolies' category) ──"
bq_q "
    SELECT DESTINATION,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE CATEGORY_TWO = 'Groceries'
    GROUP BY DESTINATION
    ORDER BY spend DESC
    LIMIT 15
"


echo
echo "── 5. THE SHARED COHORT ──"
echo "Customers who spend at BOTH Engen AND Woolworths."
echo "This is the partnership story: they're already living it."
bq_q "
    WITH engen_c AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%ENGEN%'
    ),
    woolies_c AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%WOOLWORTH%'
           OR UPPER(DESTINATION) LIKE '%WOOLIES%'
    ),
    shared AS (
        SELECT e.UNIQUE_ID FROM engen_c e
        INNER JOIN woolies_c w USING (UNIQUE_ID)
    )
    SELECT
        (SELECT COUNT(*) FROM engen_c)                                         AS engen_customers,
        (SELECT COUNT(*) FROM woolies_c)                                       AS woolies_customers,
        (SELECT COUNT(*) FROM shared)                                          AS shared_customers,
        ROUND(100.0 * (SELECT COUNT(*) FROM shared) /
              NULLIF((SELECT COUNT(*) FROM engen_c), 0), 1)                    AS pct_of_engen_shopping_woolies,
        ROUND(100.0 * (SELECT COUNT(*) FROM shared) /
              NULLIF((SELECT COUNT(*) FROM woolies_c), 0), 1)                  AS pct_of_woolies_shopping_engen,
        (SELECT COUNT(*) FROM engen_c) - (SELECT COUNT(*) FROM shared)         AS engen_only,
        (SELECT COUNT(*) FROM woolies_c) - (SELECT COUNT(*) FROM shared)       AS woolies_only
"


echo
echo "── 5b. Spend profile of the shared cohort ──"
echo "How much they spend at each brand and what an average basket looks like."
bq_q "
    WITH engen_c AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%ENGEN%'
    ),
    woolies_c AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%WOOLWORTH%'
           OR UPPER(DESTINATION) LIKE '%WOOLIES%'
    ),
    shared AS (
        SELECT e.UNIQUE_ID FROM engen_c e
        INNER JOIN woolies_c w USING (UNIQUE_ID)
    )
    SELECT
        'Engen spend by shared cohort'                                       AS metric,
        COUNT(DISTINCT cs.UNIQUE_ID)                                          AS customers,
        ROUND(SUM(cs.dest_spend), 0)                                          AS spend,
        ROUND(SUM(cs.dest_spend) / NULLIF(SUM(cs.dest_txn_count), 0), 2)      AS avg_basket,
        ROUND(SUM(cs.dest_spend) / NULLIF(COUNT(DISTINCT cs.UNIQUE_ID), 0), 0) AS spend_per_customer
    FROM \`$PROJECT.analytics.int_customer_category_spend\` cs
    WHERE UPPER(cs.DESTINATION) LIKE '%ENGEN%'
      AND cs.UNIQUE_ID IN (SELECT UNIQUE_ID FROM shared)
    UNION ALL
    SELECT
        'Woolworths spend by shared cohort'                                   AS metric,
        COUNT(DISTINCT cs.UNIQUE_ID)                                          AS customers,
        ROUND(SUM(cs.dest_spend), 0)                                          AS spend,
        ROUND(SUM(cs.dest_spend) / NULLIF(SUM(cs.dest_txn_count), 0), 2)      AS avg_basket,
        ROUND(SUM(cs.dest_spend) / NULLIF(COUNT(DISTINCT cs.UNIQUE_ID), 0), 0) AS spend_per_customer
    FROM \`$PROJECT.analytics.int_customer_category_spend\` cs
    WHERE (UPPER(cs.DESTINATION) LIKE '%WOOLWORTH%' OR UPPER(cs.DESTINATION) LIKE '%WOOLIES%')
      AND cs.UNIQUE_ID IN (SELECT UNIQUE_ID FROM shared)
"


echo
echo "── 6. Foodstop / Woolies-inside-forecourt search ──"
echo "Any distinct DESTINATION that reads like the Woolies-Foodstop concession?"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%FOODSTOP%'
       OR UPPER(DESTINATION) LIKE '%FOOD STOP%'
       OR UPPER(DESTINATION) LIKE '%FORECOURT%'
       OR UPPER(DESTINATION) LIKE '%QUICKSHOP%'
       OR UPPER(DESTINATION) LIKE '%CONVENIENCE%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 20
"


echo
echo "── 7. Engen CATEGORY_TWO check (where does Engen sit in taxonomy) ──"
bq_q "
    SELECT CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%ENGEN%'
    GROUP BY CATEGORY_TWO
    ORDER BY spend DESC
"


echo
echo "── 8. Adjacent cross-shop of shared cohort (top 10 categories) ──"
echo "What else the Engen+Woolies loyalists spend on. Bundle/co-brand angles."
bq_q "
    WITH engen_c AS (
        SELECT DISTINCT UNIQUE_ID FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%ENGEN%'
    ),
    woolies_c AS (
        SELECT DISTINCT UNIQUE_ID FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%WOOLWORTH%' OR UPPER(DESTINATION) LIKE '%WOOLIES%'
    ),
    shared AS (
        SELECT e.UNIQUE_ID FROM engen_c e JOIN woolies_c w USING (UNIQUE_ID)
    )
    SELECT
        cs.CATEGORY_TWO             AS category,
        COUNT(DISTINCT cs.UNIQUE_ID) AS shoppers,
        ROUND(SUM(cs.dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\` cs
    JOIN shared s USING (UNIQUE_ID)
    WHERE cs.CATEGORY_TWO NOT IN (
        'Fuel and Filling Stations','Groceries','Fuel','Petroleum','Filling Stations'
    )
    GROUP BY cs.CATEGORY_TWO
    ORDER BY shoppers DESC
    LIMIT 10
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo
echo "  Read section 1 to lock Engen DESTINATIONs to include."
echo "  Read section 2 to lock Woolies DESTINATIONs (Food vs main)."
echo "  Read section 5 for the shared-cohort headline (this IS the pitch)."
echo "  Read section 6 for whether Foodstop appears as its own DESTINATION."
echo "  Read section 8 for cross-shop bundling opportunities."
echo "════════════════════════════════════════════════════════════"
