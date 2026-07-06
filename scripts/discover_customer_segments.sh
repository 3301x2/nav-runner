#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Customer segment discovery — check what's actually in the unused columns.
#
# stg_customers has hyper_segment, main_banked, income_segment columns we've
# been ignoring. This script shows distinct values + counts so we can tell:
#   - Is hyper_segment the wealth tier (Entry Wallet → RMB) Leandra wants?
#   - Is main_banked the ETB/NTB flag?
#   - Is income_segment a sub-segment label we missed?
#
# Usage:
#   bash scripts/discover_customer_segments.sh [sandbox|production]
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
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty --max_rows=50 "$1" 2>/dev/null
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Customer-segment column discovery"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"

echo
echo "── 1. hyper_segment values (could be FNB wealth tier!) ──"
echo "Looking for: Entry Wallet, Entry Banking, Middle Market, Emerging"
echo "Affluent, Affluent, Wealth, UHNW, Signet, RMB"
bq_q "
    SELECT hyper_segment,
           COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\`
    GROUP BY hyper_segment
    ORDER BY customers DESC
"

echo
echo "── 2. income_segment values (could be a different segmentation) ──"
bq_q "
    SELECT income_segment,
           COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\`
    GROUP BY income_segment
    ORDER BY customers DESC
"

echo
echo "── 3. main_banked values (could be ETB/NTB flag) ──"
bq_q "
    SELECT main_banked,
           COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\`
    GROUP BY main_banked
    ORDER BY customers DESC
"

echo
echo "── 4. credit_risk_class values (bonus check) ──"
bq_q "
    SELECT credit_risk_class,
           COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\`
    GROUP BY credit_risk_class
    ORDER BY customers DESC
"

echo
echo "── 5. Cross-tab: hyper_segment × main_banked ──"
echo "If this shape matches Leandra's grid, we have the answer."
bq_q "
    SELECT hyper_segment,
           main_banked,
           COUNT(*) AS customers
    FROM \`$PROJECT.staging.stg_customers\`
    GROUP BY hyper_segment, main_banked
    ORDER BY hyper_segment, main_banked
"

echo
echo "── 6. Schema check — list all columns on stg_customers ──"
echo "(Sanity check we didn't miss other promising columns)"
bq_q "
    SELECT column_name, data_type
    FROM \`$PROJECT.staging.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'stg_customers'
    ORDER BY ordinal_position
"

echo
echo "── 7. Base table check — what's in customer_spend.base_data? ──"
echo "(stg_customers comes from base_data — maybe more columns exist there)"
bq_q "
    SELECT column_name, data_type
    FROM \`$PROJECT.customer_spend.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'base_data'
    ORDER BY ordinal_position
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. If hyper_segment has wealth-tier labels, we can populate"
echo "  Leandra's grid. If main_banked has 0/1 or Y/N, that's ETB/NTB."
echo "════════════════════════════════════════════════════════════"
