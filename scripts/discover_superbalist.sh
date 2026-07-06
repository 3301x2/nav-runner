#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Superbalist Audience Segment Discovery
#
# Leandra asked for: 9 wealth tiers × {Lead Load ETB, Lead Load NTB, Open Market ETB}
# Brief references a past campaign:
#   180k voucher-qualified + 120k Sweet-Spot Aspire = 300K total reach
#   3 months on Meta, measured via Blue Robot
#
# Wealth tiers + ETB/NTB/Open Market come from FNB customer master, not from us.
#
# This script confirms what Superbalist-relevant audiences exist in OUR data:
#   (a) Does Superbalist itself appear in DESTINATION? (size baseline)
#   (b) Fashion / apparel competitors (Zando, Spree, Mr Price, etc.)
#   (c) Sweet-Spot Aspire — likely a FNB internal segment (not in our data,
#       flag for Leandra to source)
#   (d) Voucher / digital-wallet activity patterns
#
# Usage:
#   bash scripts/discover_superbalist.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────────

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
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty --max_rows=40 "$1" 2>/dev/null
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Superbalist Audience Segment Discovery"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"
echo
echo "LEANDRA'S PAST CAMPAIGN NUMBERS (for context, not for matching):"
echo "  Audience reach:        300,000 (180k Voucher + 120k Sweet-Spot Aspire)"
echo "  Qualified for voucher: ~150k"
echo "  Claimed voucher:       ~50k  (30%)"
echo "  Chose Superbalist:     ~13k  (27%)"
echo "  Redeemed:              ~11k  (90%)"

echo
echo "── 1. Does Superbalist itself appear in DESTINATION? ──"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%SUPERBALIST%'
       OR UPPER(DESTINATION) LIKE '%SUPER BALIST%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
"

echo
echo "── 2. Online-fashion competitors (Superbalist's competitive set) ──"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%ZANDO%'
       OR UPPER(DESTINATION) LIKE '%SPREE%'
       OR UPPER(DESTINATION) LIKE '%TAKEALOT%'
       OR UPPER(DESTINATION) LIKE '%H&M%'
       OR UPPER(DESTINATION) LIKE '%H AND M%'
       OR UPPER(DESTINATION) LIKE '%COTTON ON%'
       OR UPPER(DESTINATION) LIKE '%COTTONON%'
       OR UPPER(DESTINATION) LIKE '%MR PRICE%'
       OR UPPER(DESTINATION) LIKE '%MRPRICE%'
       OR UPPER(DESTINATION) LIKE '%MR P %'
       OR UPPER(DESTINATION) LIKE '%FOSCHINI%'
       OR UPPER(DESTINATION) LIKE '%MARKHAM%'
       OR UPPER(DESTINATION) LIKE '%TRUWORTHS%'
       OR UPPER(DESTINATION) LIKE '%EDGARS%'
       OR UPPER(DESTINATION) LIKE '%WOOLWORTHS%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 30
"

echo
echo "── 3. Fashion / apparel CATEGORY_TWO values ──"
bq_q "
    SELECT CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%FASHION%'
       OR UPPER(CATEGORY_TWO) LIKE '%CLOTHING%'
       OR UPPER(CATEGORY_TWO) LIKE '%APPAREL%'
       OR UPPER(CATEGORY_TWO) LIKE '%RETAIL%'
    GROUP BY CATEGORY_TWO
    ORDER BY customers DESC
"

echo
echo "── 4. e-Commerce platform DESTINATIONs ──"
echo "(Superbalist sits on Takealot platform — context for online buying behaviour)"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%TAKEALOT%'
       OR UPPER(DESTINATION) LIKE '%MAKRO%ONLINE%'
       OR UPPER(DESTINATION) LIKE '%BASH%'
       OR UPPER(DESTINATION) LIKE '%LOOT%'
       OR UPPER(DESTINATION) LIKE '%ONEDAYONLY%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 20
"

echo
echo "── 5. Voucher / gift-card / digital-wallet activity ──"
echo "Brief mentions 'Voucher customers' — let's see what we have"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%VOUCHER%'
       OR UPPER(DESTINATION) LIKE '%GIFT CARD%'
       OR UPPER(DESTINATION) LIKE '%GIFTCARD%'
       OR UPPER(DESTINATION) LIKE '%EWALLET%'
       OR UPPER(DESTINATION) LIKE '%PREPAID%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 20
"

echo
echo "── 6. Aspire-relevant DESTINATIONs ──"
echo "'Sweet-Spot Aspire' is likely an FNB internal segment we don't have."
echo "But these are brands often associated with aspirational fashion:"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%CALVIN KLEIN%'
       OR UPPER(DESTINATION) LIKE '%TOMMY HILFIGER%'
       OR UPPER(DESTINATION) LIKE '%POLO%'
       OR UPPER(DESTINATION) LIKE '%GUESS%'
       OR UPPER(DESTINATION) LIKE '%LEVIS%'
       OR UPPER(DESTINATION) LIKE '%LEVI%'
       OR UPPER(DESTINATION) LIKE '%LACOSTE%'
       OR UPPER(DESTINATION) LIKE '%HUGO BOSS%'
       OR UPPER(DESTINATION) LIKE '%DIESEL%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 30
"

echo
echo "── 7. Total customers we could address with a fashion pitch ──"
echo "(union of Superbalist + competitors — sanity-check vs 180k voucher number)"
bq_q "
    SELECT COUNT(DISTINCT UNIQUE_ID) AS total_fashion_shoppers
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%SUPERBALIST%'
       OR UPPER(DESTINATION) LIKE '%ZANDO%'
       OR UPPER(DESTINATION) LIKE '%SPREE%'
       OR UPPER(DESTINATION) LIKE '%MR PRICE%'
       OR UPPER(DESTINATION) LIKE '%FOSCHINI%'
       OR UPPER(DESTINATION) LIKE '%TRUWORTHS%'
       OR UPPER(DESTINATION) LIKE '%EDGARS%'
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Key things to check against Leandra's brief:"
echo
echo "  • Does Superbalist appear?  →  if yes, we can scope an audience"
echo "  • Are 'Voucher' customers a real label in our data?"
echo "    (most likely NOT — it's a campaign-tracking concept)"
echo "  • 'Sweet-Spot Aspire' is almost certainly an FNB internal"
echo "    customer-master segment — we cannot replicate it from our data."
echo
echo "  If our fashion-shopper totals don't get near 180k/120k, those"
echo "  numbers came from FNB's CRM, not from us."
echo "════════════════════════════════════════════════════════════"
