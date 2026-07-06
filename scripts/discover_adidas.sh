#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Adidas Audience Segment Discovery
#
# Leandra asked for: 9 wealth tiers × {Lead Load ETB, Lead Load NTB, Open Market ETB}
# populated for 7 audiences (Gym Lovers, Sport Lovers, etc).
#
# Wealth tiers + ETB/NTB/Open Market are NOT in our data — those come from
# FNB customer master. This script confirms only what we CAN size from our
# transaction data, so we can:
#   (a) Build the 7 audiences correctly (right DESTINATIONS / categories)
#   (b) Compare our totals to Leandra's numbers and see if they match
#       (her: 218,474 / 477,730 / 278,679 / 230,768 / 31,922 / 262,690 / 214,984)
#   (c) Identify whether her grid was sourced from our data with renaming
#
# Usage:
#   bash scripts/discover_adidas.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)         PROJECT="fmn-sandbox" ;;
    production|prod|prd)    PROJECT="fmn-production-462014" ;;
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
echo "  Adidas Audience Segment Discovery"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"
echo
echo "LEANDRA'S NUMBERS (for comparison):"
echo "  1. Gym Lovers              218,474"
echo "  2. Sport Lovers            477,730"
echo "  3. Sport and Gym Lovers    278,679"
echo "  4. Spectator Ticket Buyers 230,768"
echo "  5. Participation Tickets    31,922"
echo "  6. Adidas Competitors      262,690"
echo "  7. (unlabelled)            214,984"

echo
echo "── 1. Does Adidas itself appear in DESTINATION? ──"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%ADIDAS%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
"

echo
echo "── 2. Adidas competitor brands (the 'Bespoke Competitors' row) ──"
echo "Target row 6: ~262,690 customers"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%NIKE%'
       OR UPPER(DESTINATION) LIKE '%PUMA%'
       OR UPPER(DESTINATION) LIKE '%REEBOK%'
       OR UPPER(DESTINATION) LIKE '%UNDER ARMOUR%'
       OR UPPER(DESTINATION) LIKE '%UNDERARMOUR%'
       OR UPPER(DESTINATION) LIKE '%ASICS%'
       OR UPPER(DESTINATION) LIKE '%NEW BALANCE%'
       OR UPPER(DESTINATION) LIKE '%NEWBALANCE%'
       OR UPPER(DESTINATION) LIKE '%FILA%'
       OR UPPER(DESTINATION) LIKE '%SKECHERS%'
       OR UPPER(DESTINATION) LIKE '%CONVERSE%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 30
"

echo
echo "── 3. Total customers spending at ANY Adidas competitor (deduplicated) ──"
echo "If this matches 262,690, her 'Competitors' row came from our data."
bq_q "
    SELECT COUNT(DISTINCT UNIQUE_ID) AS competitor_shoppers
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%NIKE%'
       OR UPPER(DESTINATION) LIKE '%PUMA%'
       OR UPPER(DESTINATION) LIKE '%REEBOK%'
       OR UPPER(DESTINATION) LIKE '%UNDER ARMOUR%'
       OR UPPER(DESTINATION) LIKE '%UNDERARMOUR%'
       OR UPPER(DESTINATION) LIKE '%ASICS%'
       OR UPPER(DESTINATION) LIKE '%NEW BALANCE%'
       OR UPPER(DESTINATION) LIKE '%NEWBALANCE%'
"

echo
echo "── 4. Gym-related DESTINATIONs (the 'Gym Lovers' row) ──"
echo "Target row 1: ~218,474 customers"
echo "Note: brief excludes gym membership debit orders — must be at gym LOCATIONS"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%VIRGIN ACTIVE%'
       OR UPPER(DESTINATION) LIKE '%PLANET FITNESS%'
       OR UPPER(DESTINATION) LIKE '%PLANETFITNESS%'
       OR UPPER(DESTINATION) LIKE '%CITY GYM%'
       OR UPPER(DESTINATION) LIKE '%CROSSFIT%'
       OR UPPER(DESTINATION) LIKE '%GYM%'
       OR UPPER(DESTINATION) LIKE '%FITNESS%'
       OR UPPER(DESTINATION) LIKE '%F45%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 30
"

echo
echo "── 5. Gym-related CATEGORY_TWO values ──"
bq_q "
    SELECT CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%GYM%'
       OR UPPER(CATEGORY_TWO) LIKE '%FITNESS%'
       OR UPPER(CATEGORY_TWO) LIKE '%HEALTH%CLUB%'
    GROUP BY CATEGORY_TWO
    ORDER BY customers DESC
"

echo
echo "── 6. Sporting activity DESTINATIONs (the 'Sport Lovers' row) ──"
echo "Target row 2: ~477,730 customers"
echo "Brief mentions: golf, paddle, sporting activities"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%GOLF%'
       OR UPPER(DESTINATION) LIKE '%PADDLE%'
       OR UPPER(DESTINATION) LIKE '%PADEL%'
       OR UPPER(DESTINATION) LIKE '%TENNIS%'
       OR UPPER(DESTINATION) LIKE '%SQUASH%'
       OR UPPER(DESTINATION) LIKE '%CYCLING%'
       OR UPPER(DESTINATION) LIKE '%RUNNING%'
       OR UPPER(DESTINATION) LIKE '%SWIM%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 30
"

echo
echo "── 7. Sport-related CATEGORY_TWO values ──"
bq_q "
    SELECT CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%SPORT%'
       OR UPPER(CATEGORY_TWO) LIKE '%RECREATION%'
       OR UPPER(CATEGORY_TWO) LIKE '%LEISURE%'
       OR UPPER(CATEGORY_TWO) LIKE '%ATHLETIC%'
    GROUP BY CATEGORY_TWO
    ORDER BY customers DESC
"

echo
echo "── 8. Ticketing DESTINATIONs (the 'Spectator Ticket Buyers' row) ──"
echo "Target row 4: ~230,768 customers"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%TICKET%'
       OR UPPER(DESTINATION) LIKE '%COMPUTICKET%'
       OR UPPER(DESTINATION) LIKE '%QUICKET%'
       OR UPPER(DESTINATION) LIKE '%WEBTICKET%'
       OR UPPER(DESTINATION) LIKE '%PLANKTON%'
       OR UPPER(DESTINATION) LIKE '%STADIUM%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 30
"

echo
echo "── 9. Ticketing CATEGORY_TWO values ──"
bq_q "
    SELECT CATEGORY_TWO,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(CATEGORY_TWO) LIKE '%TICKET%'
       OR UPPER(CATEGORY_TWO) LIKE '%EVENT%'
       OR UPPER(CATEGORY_TWO) LIKE '%ENTERTAIN%'
    GROUP BY CATEGORY_TWO
    ORDER BY customers DESC
"

echo
echo "── 10. Sportswear retail brands (sanity check on Adidas competitive set) ──"
bq_q "
    SELECT DESTINATION,
           COUNT(DISTINCT UNIQUE_ID) AS customers,
           ROUND(SUM(dest_spend), 0) AS spend
    FROM \`$PROJECT.analytics.int_customer_category_spend\`
    WHERE UPPER(DESTINATION) LIKE '%TOTALSPORTS%'
       OR UPPER(DESTINATION) LIKE '%TOTAL SPORTS%'
       OR UPPER(DESTINATION) LIKE '%SPORTSCENE%'
       OR UPPER(DESTINATION) LIKE '%SPORTMANS WAREHOUSE%'
       OR UPPER(DESTINATION) LIKE '%SPORTSMANS WAREHOUSE%'
       OR UPPER(DESTINATION) LIKE '%CROSS TRAINER%'
       OR UPPER(DESTINATION) LIKE '%CROSSTRAINER%'
       OR UPPER(DESTINATION) LIKE '%FOOTGEAR%'
    GROUP BY DESTINATION
    ORDER BY customers DESC
    LIMIT 20
"

echo
echo "── 11. Combined audience size — Gym AND Sport overlap (row 3) ──"
echo "Target row 3: ~278,679 customers"
echo "This computes everyone who appears in EITHER gym or sport (union)"
bq_q "
    WITH gym_customers AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(CATEGORY_TWO) LIKE '%GYM%'
           OR UPPER(CATEGORY_TWO) LIKE '%FITNESS%'
    ),
    sport_customers AS (
        SELECT DISTINCT UNIQUE_ID
        FROM \`$PROJECT.analytics.int_customer_category_spend\`
        WHERE UPPER(CATEGORY_TWO) LIKE '%SPORT%'
           OR UPPER(CATEGORY_TWO) LIKE '%RECREATION%'
    )
    SELECT
        (SELECT COUNT(*) FROM gym_customers)                              AS gym_only_or_overlap,
        (SELECT COUNT(*) FROM sport_customers)                            AS sport_only_or_overlap,
        (SELECT COUNT(*) FROM gym_customers g
            JOIN sport_customers s USING (UNIQUE_ID))                     AS both_gym_and_sport,
        (SELECT COUNT(*) FROM (
            SELECT UNIQUE_ID FROM gym_customers
            UNION DISTINCT
            SELECT UNIQUE_ID FROM sport_customers))                       AS union_gym_or_sport
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Compare the customer counts above with Leandra's numbers."
echo
echo "  If anything matches within ~5%, her grid was almost certainly"
echo "  sourced from our data with her own labelling."
echo
echo "  Next steps:"
echo "  1. Decide which DESTINATIONs / CATEGORY_TWO values define each"
echo "     audience, based on which match her counts."
echo "  2. Once Leandra confirms the wealth-tier source, build the"
echo "     final 9×3 grid script."
echo "════════════════════════════════════════════════════════════"
