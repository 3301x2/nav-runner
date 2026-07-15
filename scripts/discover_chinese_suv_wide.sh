#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Wider search for Chinese-SUV competitors as Jetour proxies.
# Excludes butcheries + food + non-vehicle categories, but doesn't require
# the CATEGORY_TWO to say "Vehicle" — some dealerships may live elsewhere.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)      PROJECT="fmn-sandbox"           ;;
    production|prod|prd) PROJECT="fmn-production-462014" ;;
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
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --location=africa-south1 \
        --format=pretty --max_rows=40 "$1"
}


echo
echo "════════════════════════════════════════════════════════════"
echo "  Wider Chinese-SUV proxy search"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. CHERY (excluding butcheries, food, etc.) ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%CHERY%'
      AND UPPER(DESTINATION) NOT LIKE '%BUTCH%'
      AND UPPER(DESTINATION) NOT LIKE '%DELI%'
      AND UPPER(DESTINATION) NOT LIKE '%MEAT%'
      AND UPPER(DESTINATION) NOT LIKE '%FOOD%'
      AND UPPER(DESTINATION) NOT LIKE '%BAKERY%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 2. HAVAL (no exclusions needed — brand name is unique) ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%HAVAL%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 3. GWM ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%GWM%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 4. MAHINDRA ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%MAHINDRA%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 5. OMODA / JAECOO / BAIC / FAW (rare Chinese brands) ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%OMODA%'
       OR UPPER(DESTINATION) LIKE '%JAECOO%'
       OR UPPER(DESTINATION) LIKE '%BAIC%'
       OR UPPER(DESTINATION) LIKE '%FAW%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 6. Combined summary — total customers across Chinese-brand DESTINATIONs ──"
bq_q "
    SELECT
        COUNT(DISTINCT UNIQUE_ID) AS unique_customers_across_all_brands,
        ROUND(SUM(dest_spend), 0) AS total_spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE (UPPER(DESTINATION) LIKE '%HAVAL%'
        OR UPPER(DESTINATION) LIKE '%GWM%'
        OR UPPER(DESTINATION) LIKE '%MAHINDRA%'
        OR UPPER(DESTINATION) LIKE '%OMODA%'
        OR UPPER(DESTINATION) LIKE '%JAECOO%'
        OR UPPER(DESTINATION) LIKE '%BAIC%'
        OR UPPER(DESTINATION) LIKE '%FAW%'
        OR (UPPER(DESTINATION) LIKE '%CHERY%'
            AND UPPER(DESTINATION) NOT LIKE '%BUTCH%'
            AND UPPER(DESTINATION) NOT LIKE '%DELI%'
            AND UPPER(DESTINATION) NOT LIKE '%MEAT%'
            AND UPPER(DESTINATION) NOT LIKE '%FOOD%'
            AND UPPER(DESTINATION) NOT LIKE '%BAKERY%'))
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo
echo "  Now we know: which of Chery/Haval/GWM/Mahindra/Omoda/Jaecoo/BAIC/FAW"
echo "  are in the data, at what scale, and how they aggregate."
echo "════════════════════════════════════════════════════════════"
