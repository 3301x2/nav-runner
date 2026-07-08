#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Discover Suzuki + Jetour + comparable-brand DESTINATIONs in one screen.
#
# Output is horizontal — brand name column narrow, all key metrics wide,
# so you can screenshot 2-3 sections per shot instead of 20.
#
# Sections:
#   1. Suzuki dealerships (SUZUKI variants + parts/service)
#   2. Jetour (if it exists at all)
#   3. Value-Chinese SUV competitive set (Chery / Haval / GWM / Mahindra)
#      — used as Jetour proxy
#   4. Vehicle-related CATEGORY_TWO values (context)
#   5. Auto-sales top 20 (context for Suzuki competitors)
#
# Usage:
#   bash scripts/discover_suzuki_jetour.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)      PROJECT="fmn-sandbox"           ;;
    production|prod|prd) PROJECT="fmn-production-462014" ;;
    *) echo "Usage: bash $0 [sandbox|production]"; exit 1 ;;
esac

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login --update-adc --quiet || exit 1
fi

# Wide table — 200 char width, unlimited results but capped per section
bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
        --format=pretty --max_rows=25 "$1" 2>/dev/null
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Suzuki + Jetour DESTINATION discovery"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Suzuki dealerships / service (any DESTINATION with SUZUKI) ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID)  AS customers,
           SUM(dest_txn_count)        AS transactions,
           ROUND(SUM(dest_spend), 0)  AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%SUZUKI%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 2. Jetour (any DESTINATION mentioning JETOUR) ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           SUM(dest_txn_count)       AS transactions,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%JETOUR%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 3. Value-Chinese SUV competitive set (Jetour proxy candidates) ──"
echo "(matches only vehicle-related DESTINATIONs — excludes butcheries etc.)"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE (UPPER(CATEGORY_TWO) LIKE '%VEHICLE%'
        OR UPPER(CATEGORY_TWO) LIKE '%MOTOR%'
        OR UPPER(CATEGORY_TWO) LIKE '%DEALER%'
        OR UPPER(CATEGORY_TWO) LIKE '%AUTO%')
      AND (UPPER(DESTINATION) LIKE '%CHERY%'
        OR UPPER(DESTINATION) LIKE '%HAVAL%'
        OR UPPER(DESTINATION) LIKE '%GWM%'
        OR UPPER(DESTINATION) LIKE '%MAHINDRA%'
        OR UPPER(DESTINATION) LIKE '%OMODA%'
        OR UPPER(DESTINATION) LIKE '%FAW%'
        OR UPPER(DESTINATION) LIKE '%BAIC%'
        OR UPPER(DESTINATION) LIKE '%JAECOO%')
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 4. Vehicle-related CATEGORY_TWO values ──"
bq_q "
    SELECT CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           SUM(dest_txn_count)       AS transactions,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%VEHICLE%'
       OR UPPER(CATEGORY_TWO) LIKE '%MOTOR%'
       OR UPPER(CATEGORY_TWO) LIKE '%AUTO%'
       OR UPPER(CATEGORY_TWO) LIKE '%CAR%'
       OR UPPER(CATEGORY_TWO) LIKE '%DEALER%'
    GROUP BY CATEGORY_TWO
    ORDER BY spend DESC
    LIMIT 15
"


echo
echo "── 5. Top 20 auto brands (context — Suzuki's competitive set) ──"
echo "(pulls the top-spend DESTINATIONs in vehicle-shaped categories)"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%VEHICLE%'
       OR UPPER(CATEGORY_TWO) LIKE '%MOTOR%'
       OR UPPER(CATEGORY_TWO) LIKE '%DEALER%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 20
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo
echo "  Read Section 1 to decide which SUZUKI DESTINATIONs to include."
echo "  Read Section 2 to see if Jetour appears at all."
echo "  Read Section 3 to pick Jetour proxy competitors."
echo "════════════════════════════════════════════════════════════"
