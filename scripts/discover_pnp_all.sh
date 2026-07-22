#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# ONE script, everything for the Tuesday PnP unlock deck.
#
# v2 fixes:
#   - ROWS reserved-word bug in A2/A3 (alias as n_rows)
#   - Hash normalization diagnostic: check if LR uses lowercase-first, phone
#     as identifier, salted hash, etc.
#   - Adds inventory + schema + sample of the 3 eBucks prod tables
#   - Overlap uses LOWER() on both sides in case that's the fix
#
# Read-only everywhere. Screenshot-friendly.
#
# Usage:
#   bash scripts/discover_pnp_all.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

# Mirror everything to a log file so nothing scrolls off screen.
LOG="$HOME/pnp_discovery.log"
exec > >(tee "$LOG") 2>&1

echo "Full output is being written to $LOG"
echo "After the run, page through it with: less -R $LOG"
echo

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    gcloud auth application-default login
fi

PROD="fmn-production-462014"
SB="fmn-sandbox"
FRG="\`$PROD.PicknPay.Audience_Upload_20260206\`"

bq_prod() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}
bq_sb() {
    bq query --quiet --use_legacy_sql=false --project_id="$SB" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

hdr() {
    echo
    echo "════════════════════════════════════════════════════════════"
    echo "  $1"
    echo "════════════════════════════════════════════════════════════"
}

hdr "PnP UNLOCK DECK v2, one-shot discovery"


# ═════════════════════════════════════════════════════════════════════
# PART A: DATASET INVENTORY (fixed ROWS bug)
# ═════════════════════════════════════════════════════════════════════

hdr "A1. Every prod dataset with table count"
for ds in Adidas ETL_DEV Metropolitan PicknPay demographics_customer \
          demographics_fld demographics_mb staging; do
    n=$(bq --project_id="$PROD" --location=africa-south1 \
        ls --max_results=200 "$PROD:$ds" 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
    echo "  $ds: $n tables"
done


hdr "A2. Prod PicknPay tables + row counts"
bq_prod "
    SELECT t.table_name, p.n_rows
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name, SUM(total_rows) AS n_rows
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE t.table_type = 'BASE TABLE'
    ORDER BY p.n_rows DESC NULLS LAST
"


hdr "A3. LR mirrors in sandbox (pnp_liveramp) + row counts"
bq_sb "
    SELECT t.table_name, p.n_rows
    FROM \`$SB.pnp_liveramp.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name, SUM(total_rows) AS n_rows
        FROM \`$SB.pnp_liveramp.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE t.table_type = 'BASE TABLE'
    ORDER BY p.n_rows DESC NULLS LAST
"


# ═════════════════════════════════════════════════════════════════════
# PART B: VERIFY PNP SLIDE CLAIMS
# ═════════════════════════════════════════════════════════════════════

hdr "B1. VERIFY: PnP slide 5 pyramid vs our FRG buckets"
bq_prod "
    WITH bucketed AS (
        SELECT CASE
            WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL       THEN '4. Lapsed proxy: no PnP spend'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.10 THEN '3. Tertiary proxy: <10%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.30 THEN '2. Secondary proxy: 10-30%'
            ELSE                                                     '1. Primary proxy: 30%+'
        END AS pnp_bucket
        FROM $FRG WHERE val_tot_trns > 0
    )
    SELECT pnp_bucket, COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_frg
    FROM bucketed GROUP BY pnp_bucket ORDER BY pnp_bucket
"


hdr "B2. VERIFY: FRG reach"
bq_prod "
    SELECT COUNT(*) AS frg_customers,
           COUNTIF(nr_pnp_trns > 0) AS pnp_active_in_frg,
           ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1) AS pct_active
    FROM $FRG
"


# ═════════════════════════════════════════════════════════════════════
# PART C: FRG CROSS-TABS (already validated, keep for completeness)
# ═════════════════════════════════════════════════════════════════════

hdr "C1. Retail_Model x PnP behaviour"
bq_prod "
    SELECT Retail_Model, COUNT(*) AS customers,
           COUNTIF(nr_pnp_trns > 0) AS pnp_active,
           ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1) AS active_pct,
           ROUND(AVG(val_pnp_trns), 0) AS avg_pnp_spend,
           ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_wallet_pct,
           ROUND(SUM(val_pnp_trns) / 1e6, 1) AS total_pnp_m
    FROM $FRG WHERE val_tot_trns > 0
    GROUP BY Retail_Model ORDER BY total_pnp_m DESC
"


hdr "C2. Wallet-share headroom buckets"
bq_prod "
    WITH bucketed AS (
        SELECT CASE
            WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL       THEN '0. No PnP spend'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.05 THEN '1. Under 5%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.10 THEN '2. 5-10%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.20 THEN '3. 10-20%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.40 THEN '4. 20-40%'
            ELSE                                                     '5. 40%+'
        END AS bucket, val_pnp_trns, val_tot_trns
        FROM $FRG WHERE val_tot_trns > 0
    )
    SELECT bucket, COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
           ROUND(SUM(val_pnp_trns) / 1e6, 1) AS pnp_spend_m,
           ROUND(SUM(val_tot_trns) / 1e6, 1) AS total_spend_m
    FROM bucketed GROUP BY bucket ORDER BY bucket
"


hdr "C3. Grocery-delivery adoption (ASAP wealth gradient)"
bq_prod "
    SELECT Retail_Model, COUNT(*) AS customers,
           COUNTIF(grocery_delivery_trns > 0) AS delivery_users,
           ROUND(100.0 * COUNTIF(grocery_delivery_trns > 0) / COUNT(*), 1) AS adoption_pct
    FROM $FRG GROUP BY Retail_Model ORDER BY adoption_pct DESC
"


# ═════════════════════════════════════════════════════════════════════
# PART D: EBUCKS TABLES (NEW — 3 prod tables we haven't queried)
# ═════════════════════════════════════════════════════════════════════

hdr "D1. eBucks table schemas in prod PicknPay"
bq_prod "
    SELECT table_name, column_name, data_type
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE LOWER(table_name) LIKE '%ebucks%'
       OR LOWER(table_name) LIKE '%burger%'
       OR LOWER(table_name) LIKE '%payday%'
    ORDER BY table_name, ordinal_position
"


hdr "D2. Row counts for eBucks tables"
bq_prod "
    SELECT t.table_name, p.n_rows
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name, SUM(total_rows) AS n_rows
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE LOWER(t.table_name) LIKE '%ebucks%'
       OR LOWER(t.table_name) LIKE '%burger%'
       OR LOWER(t.table_name) LIKE '%payday%'
    ORDER BY p.n_rows DESC NULLS LAST
"


hdr "D3. eBucks BurgerFriday sample rows"
bq_prod "SELECT * FROM \`$PROD.PicknPay.PNP_eBucks_BurgerFriday\` LIMIT 3"

hdr "D4. eBucks payday sample rows (case A)"
bq_prod "SELECT * FROM \`$PROD.PicknPay.PNP_payday_ebucks_202512\` LIMIT 3"


# ═════════════════════════════════════════════════════════════════════
# PART E: JOIN KEY DIAGNOSTICS (why did overlap fail?)
# ═════════════════════════════════════════════════════════════════════

hdr "E1. FRG EMAIL_ADDR format sanity"
bq_prod "
    SELECT LENGTH(EMAIL_ADDR) AS len,
           REGEXP_CONTAINS(EMAIL_ADDR, r'^[0-9a-f]{64}\$') AS is_lower_sha256,
           REGEXP_CONTAINS(EMAIL_ADDR, r'^[0-9A-Fa-f]{64}\$') AS is_any_hex_sha256,
           COUNT(*) AS n
    FROM $FRG WHERE EMAIL_ADDR IS NOT NULL
    GROUP BY len, is_lower_sha256, is_any_hex_sha256
    ORDER BY n DESC LIMIT 5
"


hdr "E2. LR pnp_audiences_for_awareness format sanity"
bq_sb "
    SELECT LENGTH(string_field_0) AS len,
           REGEXP_CONTAINS(string_field_0, r'^[0-9a-f]{64}\$') AS is_lower_sha256,
           REGEXP_CONTAINS(string_field_0, r'^[0-9A-Fa-f]{64}\$') AS is_any_hex_sha256,
           COUNT(*) AS n
    FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\`
    WHERE string_field_0 IS NOT NULL
    GROUP BY len, is_lower_sha256, is_any_hex_sha256
    ORDER BY n DESC LIMIT 5
"


hdr "E3. LR ntb_transact EMAIL format sanity"
bq_sb "
    SELECT LENGTH(EMAIL) AS len,
           REGEXP_CONTAINS(EMAIL, r'^[0-9a-f]{64}\$') AS is_lower_sha256,
           REGEXP_CONTAINS(EMAIL, r'^[0-9A-Fa-f]{64}\$') AS is_any_hex_sha256,
           COUNT(*) AS n
    FROM \`$SB.pnp_liveramp.lr_out_ntb_transact\`
    WHERE EMAIL IS NOT NULL
    GROUP BY len, is_lower_sha256, is_any_hex_sha256
    ORDER BY n DESC LIMIT 5
"


hdr "E4. LR clothing_base email_addr format sanity (this one JOINED 95%)"
bq_sb "
    SELECT LENGTH(email_addr) AS len,
           REGEXP_CONTAINS(email_addr, r'^[0-9a-f]{64}\$') AS is_lower_sha256,
           COUNT(*) AS n
    FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    WHERE email_addr IS NOT NULL
    GROUP BY len, is_lower_sha256 ORDER BY n DESC LIMIT 5
"


hdr "E5. Sample 3 emails from each LR table, side-by-side"
echo "FRG (Audience_Upload):"
bq_prod "SELECT SUBSTR(EMAIL_ADDR, 1, 20) AS email_prefix FROM $FRG WHERE EMAIL_ADDR IS NOT NULL LIMIT 3"
echo "LR pnp_audiences_for_awareness:"
bq_sb "SELECT SUBSTR(string_field_0, 1, 20) AS email_prefix FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\` WHERE string_field_0 IS NOT NULL LIMIT 3"
echo "LR ntb_transact:"
bq_sb "SELECT SUBSTR(EMAIL, 1, 20) AS email_prefix FROM \`$SB.pnp_liveramp.lr_out_ntb_transact\` WHERE EMAIL IS NOT NULL LIMIT 3"
echo "LR clothing_base (the one that joined 95%):"
bq_sb "SELECT SUBSTR(email_addr, 1, 20) AS email_prefix FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\` WHERE email_addr IS NOT NULL LIMIT 3"


hdr "E6. Retry pnp_audiences_for_awareness overlap using LOWER() on both sides"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT LOWER(string_field_0) AS email
        FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\`
    )
    SELECT COUNT(DISTINCT f.EMAIL_ADDR) AS overlap_lower
    FROM $FRG f
    JOIN lr l ON LOWER(f.EMAIL_ADDR) = l.email
"


# ═════════════════════════════════════════════════════════════════════
# PART F: THE KILLER STATS (using clothing_base, the join that worked)
# ═════════════════════════════════════════════════════════════════════

hdr "F1. FRG Retail_Model mix INSIDE clothing_base (696k customers matched)"
echo "This is deck-worthy: who are the FRG customers who shop PnP Clothing?"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    )
    SELECT f.Retail_Model,
           COUNT(*) AS matched,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_matches,
           COUNTIF(l.SmartShopper_Indicator = 'Y') AS is_ss_member,
           ROUND(100.0 * COUNTIF(l.SmartShopper_Indicator = 'Y') / COUNT(*), 1) AS ss_penetration_pct
    FROM $FRG f
    JOIN lr l ON f.EMAIL_ADDR = l.email_addr
    GROUP BY f.Retail_Model
    ORDER BY matched DESC
"


hdr "F2. Clothing shoppers: PnP-spend behaviour by Smart Shopper Y/N"
echo "Do Smart Shopper members spend more at PnP than non-members?"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    )
    SELECT l.SmartShopper_Indicator,
           COUNT(*) AS customers,
           ROUND(AVG(f.val_pnp_trns), 0) AS avg_pnp_spend,
           ROUND(AVG(f.val_tot_trns), 0) AS avg_total_spend,
           ROUND(AVG(SAFE_DIVIDE(f.val_pnp_trns, f.val_tot_trns)) * 100, 1) AS wallet_pct
    FROM $FRG f
    JOIN lr l ON f.EMAIL_ADDR = l.email_addr
    WHERE f.val_tot_trns > 0
    GROUP BY l.SmartShopper_Indicator
"


hdr "F3. Clothing shoppers by MBD_Tier x SmartShopper (activation matrix)"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    )
    SELECT f.MBD_Tier, l.SmartShopper_Indicator,
           COUNT(*) AS matched,
           ROUND(AVG(f.val_pnp_trns), 0) AS avg_pnp_spend
    FROM $FRG f
    JOIN lr l ON f.EMAIL_ADDR = l.email_addr
    WHERE f.MBD_Tier IS NOT NULL
    GROUP BY f.MBD_Tier, l.SmartShopper_Indicator
    ORDER BY f.MBD_Tier, l.SmartShopper_Indicator
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Priority screenshots for me:"
echo "    Part D (eBucks table schemas) — new data source"
echo "    Part E5 (email prefixes side-by-side) — reveals hash mismatch"
echo "    Part E6 (LOWER() retry) — did the fix work?"
echo "    Part F (clothing_base joins) — deck-worthy stats"
echo "════════════════════════════════════════════════════════════"
