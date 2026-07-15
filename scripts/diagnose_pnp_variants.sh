#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Diagnose PnP banner data quality.
#
# The Group pitch shows some PnP sub-banners with suspiciously tiny
# footprints (Liquor 20k, Pharmacy 2k, VAS 2k, Travel 177). That could
# mean either:
#   (a) FNB card-swipe data legitimately doesn't see much activity there
#       because most PnP transactions swipe as the parent merchant, or
#   (b) The transactions ARE in the data but under a different DESTINATION
#       spelling we're missing (PNP LIQUOR, PICKNPAY PHARMACY, etc.)
#
# This script:
#   1. Lists every DESTINATION starting with PICK, PNP, or containing "PICK N PAY"
#   2. Sums Group hero vs sum-of-banners naively (do they reconcile?)
#   3. Checks CATEGORY_TWO distribution — is Liquor spend leaking into
#      the flagship PICK N PAY DESTINATION under CATEGORY_TWO='Liquor Stores'?
#   4. Sample transactions per small banner (are those 20k Liquor customers
#      really shopping liquor, or is it a data mislabel?)
#
# Usage:
#   bash scripts/diagnose_pnp_variants.sh [sandbox|production]
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
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
        --location=africa-south1 --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  PnP variants diagnostic"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. EVERY DESTINATION starting PICK, PNP, or matching pattern ──"
echo "(catches missed variants: 'PNP LIQUOR', 'PICKNPAY EXPRESS' etc.)"
bq_q "
    SELECT DESTINATION, CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE 'PICK%'
       OR UPPER(DESTINATION) LIKE 'PNP%'
       OR UPPER(DESTINATION) LIKE '%PICKNPAY%'
       OR UPPER(DESTINATION) LIKE '%PICK N PAY%'
       OR UPPER(DESTINATION) LIKE '%P N P%'
    GROUP BY DESTINATION, CATEGORY_TWO
    ORDER BY customers DESC
    LIMIT 50
"


echo
echo "── 2. Sum-of-banners vs deduped-Group reconciliation ──"
echo "Naive sum of per-banner spend SHOULD be higher than deduped Group spend"
echo "because Group deduplicates customers only, not spend. Spend is additive."
bq_q "
    WITH per_banner AS (
        SELECT
            DESTINATION,
            SUM(dest_spend) AS banner_spend,
            SUM(dest_txn_count) AS banner_txns
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) IN (
            'PICK N PAY','PICK N PAY EXPRESS','PICK N PAY ASAP',
            'PICK N PAY CLOTHING','PICK N PAY LIQUOR','PNP PHARMACY',
            'PICK N PAY VAS','PICK N PAY TRAVEL'
        )
        GROUP BY DESTINATION
    ),
    grp AS (
        SELECT
            SUM(dest_spend) AS group_spend,
            SUM(dest_txn_count) AS group_txns
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) IN (
            'PICK N PAY','PICK N PAY EXPRESS','PICK N PAY ASAP',
            'PICK N PAY CLOTHING','PICK N PAY LIQUOR','PNP PHARMACY',
            'PICK N PAY VAS','PICK N PAY TRAVEL'
        )
    )
    SELECT
        ROUND((SELECT SUM(banner_spend) FROM per_banner), 0) AS sum_of_banners_spend,
        ROUND((SELECT group_spend FROM grp), 0)              AS group_query_spend,
        (SELECT SUM(banner_txns) FROM per_banner)            AS sum_of_banners_txns,
        (SELECT group_txns FROM grp)                         AS group_query_txns
"


echo
echo "── 3. CATEGORY_TWO leakage inside 'PICK N PAY' flagship ──"
echo "Does the flagship DESTINATION carry Liquor / Pharmacy / VAS spend"
echo "under different CATEGORY_TWO values? If yes, those sub-banners"
echo "are under-reported in our per-banner split."
bq_q "
    SELECT
        CATEGORY_TWO,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        SUM(dest_txn_count)       AS transactions,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) = 'PICK N PAY'
    GROUP BY CATEGORY_TWO
    ORDER BY spend DESC
    LIMIT 20
"


echo
echo "── 4. Sample transactions per small banner ──"
echo "(sanity: are these txns actually in the categories we'd expect?)"

for banner in "PICK N PAY LIQUOR" "PNP PHARMACY" "PICK N PAY VAS" "PICK N PAY TRAVEL"; do
    echo
    echo "  ── ${banner} ──"
    bq_q "
        SELECT
            DESTINATION,
            CATEGORY_TWO,
            COUNT(DISTINCT UNIQUE_ID) AS customers,
            SUM(dest_txn_count)       AS transactions,
            ROUND(SUM(dest_spend), 0) AS spend,
            ROUND(SUM(dest_spend) / NULLIF(SUM(dest_txn_count), 0), 2) AS avg_txn
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) = '${banner}'
        GROUP BY DESTINATION, CATEGORY_TWO
    "
done


echo
echo "── 5. All Liquor Stores destinations (competitive) ──"
echo "If PnP Liquor is really only 20k customers, what's TOPS / Norman"
echo "Goodfellows / Ultra Liquors doing? Gives context for whether 20k"
echo "is genuinely low or suspicious."
bq_q "
    SELECT DESTINATION,
        COUNT(DISTINCT UNIQUE_ID) AS customers,
        ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE CATEGORY_TWO = 'Liquor Stores'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 15
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Read section 1: are we missing any PnP variants?"
echo "  Read section 2: does sum-of-banners reconcile to Group?"
echo "  Read section 3: is Liquor/Pharmacy spend hidden inside flagship?"
echo "  Read section 4: sanity per small banner."
echo "  Read section 5: is 20k PnP Liquor customers reasonable vs peers?"
echo "════════════════════════════════════════════════════════════"
