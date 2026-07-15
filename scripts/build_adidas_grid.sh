#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Adidas Sub-Segment Grid Builder
#
# Populates Leandra's 9-tier × 3-column table for Adidas shoppers.
# Mirrors build_superbalist_grid.sh — same decoder, same assumptions.
#
# Mapping (Pierre 24 Jun WhatsApp):
#   EL*  → Entry Wallet
#   EU*  → Entry Banking
#   GL*  → Middle Market
#   PB*  → Emerging Affluent
#   PC*  → Affluent
#   PW0  → Wealth (note: aggregates with PWU + PWH per Pierre)
#   PWU  → Ultra High Net Worth
#   PWH  → High Net Worth
#   ?    → Signet, RMB (cannot identify from our data — flag in output)
#
# Usage:
#   bash scripts/build_adidas_grid.sh [sandbox|production]
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
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --location=africa-south1 --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  ADIDAS | Audience Sub-Segment Grid"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"
echo
echo "ASSUMPTIONS (per Pierre, 24 Jun WhatsApp):"
echo "  • All FNB cardholders → ETB (Existing-to-Bank)"
echo "  • NTB and Open Market columns = 0 (no source in our data)"
echo "  • Wealth row aggregates PW0 + PWU + PWH (combined wealth base)"
echo "  • Signet / RMB cannot be separated from Wealth — flagged below"

echo
echo "── 1. Confirm Adidas customer base ──"
bq_q "
    SELECT
        COUNT(DISTINCT UNIQUE_ID)  AS adidas_customers,
        ROUND(SUM(dest_spend), 0)  AS total_spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%ADIDAS%'
"

echo
echo "── 2. THE GRID — Lead Load Volumes (ETB) by sub-segment ──"
echo "  This is the populated table for Leandra's deliverable."
bq_q "
    WITH adidas_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%ADIDAS%'
    ),
    decoded AS (
        SELECT
            s.UNIQUE_ID,
            CASE
                WHEN c.income_segment LIKE 'EL%' THEN '1. Entry Wallet'
                WHEN c.income_segment LIKE 'EU%' THEN '2. Entry Banking'
                WHEN c.income_segment LIKE 'GL%' THEN '3. Middle Market'
                WHEN c.income_segment LIKE 'PB%' THEN '4. Emerging Affluent'
                WHEN c.income_segment LIKE 'PC%' THEN '5. Affluent'
                WHEN c.income_segment IN ('PW0', 'PWU', 'PWH') THEN '6. Wealth (PW0+PWU+PWH)'
                ELSE '9. Unknown / Other'
            END AS sub_segment
        FROM adidas_custs s
        LEFT JOIN \`$PROJECT.staging.stg_customers\` c USING (UNIQUE_ID)
    )
    SELECT
        sub_segment,
        COUNT(*)                                                AS lead_load_etb,
        0                                                       AS lead_load_ntb,
        0                                                       AS open_market_etb,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)      AS pct_of_audience
    FROM decoded
    GROUP BY sub_segment
    ORDER BY sub_segment
"

echo
echo "── 3. Wealth-row detail (in case Leandra needs the split) ──"
echo "  Pierre flagged that 'Signer customers' = subset of Wealth that"
echo "  may need to be removed. We can't identify Signers separately."
bq_q "
    WITH adidas_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%ADIDAS%'
    )
    SELECT
        c.income_segment AS raw_code,
        COUNT(*)         AS customers
    FROM adidas_custs s
    JOIN \`$PROJECT.staging.stg_customers\` c USING (UNIQUE_ID)
    WHERE c.income_segment IN ('PW0', 'PWU', 'PWH')
    GROUP BY c.income_segment
    ORDER BY raw_code
"

echo
echo "── 4. Coverage check — how many Adidas customers have a code? ──"
bq_q "
    WITH adidas_custs AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(DESTINATION) LIKE '%ADIDAS%'
    )
    SELECT
        COUNT(*) AS total,
        COUNTIF(c.income_segment IS NOT NULL) AS with_code,
        COUNTIF(c.income_segment IS NULL)     AS missing_code,
        ROUND(100.0 * COUNTIF(c.income_segment IS NULL) / COUNT(*), 2) AS pct_missing
    FROM adidas_custs s
    LEFT JOIN \`$PROJECT.staging.stg_customers\` c USING (UNIQUE_ID)
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo
echo "  Section 2 IS the table for Leandra."
echo "  Caveats to include in the cover note:"
echo "    1. All volumes in ETB column — no NTB / Open Market available"
echo "    2. Wealth row combines PW0 + PWU + PWH (Pierre's instruction)"
echo "    3. Signet & RMB rows: cannot be separated from Wealth"
echo
echo "  NOTE: This is direct-Adidas-shoppers. If Leandra wants the grid"
echo "  broken by her 7 audiences (Gym Lovers / Sport Lovers / etc.),"
echo "  that's a separate 9×7 = 63-cell script. Ask first."
echo "════════════════════════════════════════════════════════════"
