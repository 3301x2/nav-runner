#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Discover Takealot + Pick n Pay DESTINATIONs in one shot, plus their
# competitive set, so we can build direct-mode pitches for both.
#
# Output kept horizontal so it screenshots cleanly (2-3 sections per pic).
#
# Sections:
#   1. Takealot DESTINATION variants
#   2. Pick n Pay DESTINATION variants (Market, Hyper, Clothing, Liquor, etc.)
#   3. Groceries top 15 (PnP competitive set — Checkers, Woolies, Shoprite...)
#   4. E-commerce / Online-retail top 15 (Takealot competitive set)
#   5. CATEGORY_TWO check — what categories do PnP and Takealot live in
#
# Usage:
#   bash scripts/discover_takealot_pnp.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-production}"
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
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
        --location=africa-south1 \
        --format=pretty --max_rows=25 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Takealot + Pick n Pay DESTINATION discovery"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Takealot DESTINATION variants ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID)  AS customers,
           SUM(dest_txn_count)        AS transactions,
           ROUND(SUM(dest_spend), 0)  AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%TAKEALOT%'
       OR UPPER(DESTINATION) LIKE '%TAKE ALOT%'
       OR UPPER(DESTINATION) LIKE '%TAKE-A-LOT%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 2. Pick n Pay DESTINATION variants ──"
echo "(catches PnP, PICK N PAY, PICK-N-PAY, PNP variants across sub-brands)"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID)  AS customers,
           SUM(dest_txn_count)        AS transactions,
           ROUND(SUM(dest_spend), 0)  AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%PICK N PAY%'
       OR UPPER(DESTINATION) LIKE '%PICK-N-PAY%'
       OR UPPER(DESTINATION) LIKE '%PICKNPAY%'
       OR UPPER(DESTINATION) LIKE 'PNP%'
       OR UPPER(DESTINATION) LIKE '% PNP %'
       OR UPPER(DESTINATION) LIKE '%PNP HYPER%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 25
"


echo
echo "── 3. Groceries top 15 (PnP competitive set) ──"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID)  AS customers,
           ROUND(SUM(dest_spend), 0)  AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE CATEGORY_TWO = 'Groceries'
    GROUP BY DESTINATION
    ORDER BY spend DESC
    LIMIT 15
"


echo
echo "── 4. E-commerce / Online retail top 15 (Takealot competitive set) ──"
echo "(looks in Online / E-commerce / General Retail categories)"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID)  AS customers,
           ROUND(SUM(dest_spend), 0)  AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%ONLINE%'
       OR UPPER(CATEGORY_TWO) LIKE '%E-COMMERCE%'
       OR UPPER(CATEGORY_TWO) LIKE '%ECOMMERCE%'
       OR UPPER(CATEGORY_TWO) LIKE '%DIGITAL%'
       OR UPPER(CATEGORY_TWO) LIKE '%DEPARTMENT%'
       OR UPPER(CATEGORY_TWO) LIKE '%GENERAL RETAIL%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY spend DESC
    LIMIT 15
"


echo
echo "── 5. CATEGORY_TWO check — where do PnP and Takealot live? ──"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID)  AS customers,
           ROUND(SUM(dest_spend), 0)  AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%TAKEALOT%'
       OR UPPER(DESTINATION) LIKE '%PICK N PAY%'
       OR UPPER(DESTINATION) LIKE 'PNP%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY spend DESC
    LIMIT 25
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo
echo "  Read Section 1 to lock exact Takealot DESTINATIONs to include."
echo "  Read Section 2 to lock PnP DESTINATIONs (there may be multiple"
echo "  banners — Market vs Hyper vs Clothing — decide whether to combine)."
echo "  Read Section 3 for PnP's competitive story."
echo "  Read Section 4 for Takealot's competitive story."
echo "════════════════════════════════════════════════════════════"
