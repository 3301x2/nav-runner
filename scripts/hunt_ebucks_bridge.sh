#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Hunt for a way to join FRG (email hash) to eBucks (cust_id_reg_no).
#
# eBucks tables use cust_id_reg_no + reward_seg_id.
# FRG Audience_Upload uses EMAIL_ADDR + CUST_CELL_NO.
#
# We need one of:
#   (a) A cust_id_reg_no column somewhere in FRG so we join direct
#   (b) A bridge table with BOTH email_addr AND cust_id_reg_no
#   (c) A reward_seg_id column already in FRG (skips the join entirely)
#
# Read-only.
#
# Usage:
#   bash scripts/hunt_ebucks_bridge.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

LOG="$HOME/ebucks_bridge.log"
exec > >(tee "$LOG") 2>&1
echo "Full output at $LOG"
echo

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    gcloud auth application-default login
fi

PROD="fmn-production-462014"
SB="fmn-sandbox"

bq_prod() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

hdr() {
    echo
    echo "════════════════════════════════════════════════════════════"
    echo "  $1"
    echo "════════════════════════════════════════════════════════════"
}

hdr "eBucks bridge discovery"


# ── 1. Does FRG Audience_Upload have a cust_id_reg_no column? ──────────
hdr "1. FRG Audience_Upload_20260206 full column list"
bq_prod "
    SELECT column_name, data_type, ordinal_position
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'Audience_Upload_20260206'
    ORDER BY ordinal_position
"


# ── 2. Any prod table with BOTH cust_id_reg_no AND email_addr? ─────────
hdr "2. Every prod PicknPay table with cust_id_reg_no OR reward_seg_id"
bq_prod "
    SELECT table_name,
           STRING_AGG(column_name ORDER BY ordinal_position) AS cols
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE LOWER(column_name) LIKE '%cust_id_reg%'
       OR LOWER(column_name) LIKE '%reward_seg%'
    GROUP BY table_name
    ORDER BY table_name
"


# ── 3. Prod PicknPay tables with BOTH email AND cust_id_reg_no ─────────
hdr "3. PicknPay tables with BOTH email/mobile AND cust_id_reg_no (bridges)"
bq_prod "
    WITH cust_id_tables AS (
        SELECT DISTINCT table_name
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
        WHERE LOWER(column_name) LIKE '%cust_id_reg%'
    ),
    email_tables AS (
        SELECT DISTINCT table_name
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
        WHERE LOWER(column_name) IN
            ('email_addr','email','hem','hashed_email','sha256_email',
             'mobile','msisdn','cell','cust_cell_no')
    )
    SELECT c.table_name AS bridge_candidate,
           (SELECT STRING_AGG(column_name ORDER BY ordinal_position)
            FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
            WHERE table_name = c.table_name) AS all_cols
    FROM cust_id_tables c
    INNER JOIN email_tables e USING (table_name)
    ORDER BY c.table_name
"


# ── 4. latest_fnb_trns_base full schema (5.76M rows, likely the bridge) ─
hdr "4. latest_fnb_trns_base schema (5.76M rows, the likely bridge table)"
bq_prod "
    SELECT column_name, data_type, ordinal_position
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'latest_fnb_trns_base'
    ORDER BY ordinal_position
"


# ── 5. LiveRamp_POC_Campaign_Extract schema (already known has mobile,
#    cust_id_reg_no, reward_seg_id) — how big is this bridge? ──────────
hdr "5. LiveRamp_POC_Campaign_Extract schema + sample"
bq_prod "
    SELECT column_name, data_type
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'LiveRamp_POC_Campaign_Extract'
    ORDER BY ordinal_position
"
bq_prod "SELECT * FROM \`$PROD.PicknPay.LiveRamp_POC_Campaign_Extract\` LIMIT 3"


# ── 6. reward_seg_id distinct values (the eBucks tiers) ────────────────
hdr "6. Distinct reward_seg_id values in PNP_eBucks_BurgerFriday"
bq_prod "
    SELECT reward_seg_id, COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM \`$PROD.PicknPay.PNP_eBucks_BurgerFriday\`
    GROUP BY reward_seg_id
    ORDER BY customers DESC
"


# ── 7. Same for payday ───────────────────────────────────────────────
hdr "7. Distinct reward_seg_id values in PNP_payday_ebucks_202512"
bq_prod "
    SELECT reward_seg_id, COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct
    FROM \`$PROD.PicknPay.PNP_payday_ebucks_202512\`
    GROUP BY reward_seg_id
    ORDER BY customers DESC
"


# ── 8. Overlap: eBucks BurgerFriday cust_id_reg_no x LR POC Extract ──
hdr "8. eBucks BurgerFriday x LiveRamp_POC_Campaign_Extract overlap"
echo "If LiveRamp_POC_Campaign_Extract has both cust_id_reg_no AND email,"
echo "this is the bridge: join FRG on email, LR_POC on email, then bring"
echo "reward_seg_id from eBucks via cust_id_reg_no."
bq_prod "
    WITH ebucks AS (
        SELECT DISTINCT cust_id_reg_no FROM \`$PROD.PicknPay.PNP_eBucks_BurgerFriday\`
    ),
    poc AS (
        SELECT DISTINCT cust_id_reg_no FROM \`$PROD.PicknPay.LiveRamp_POC_Campaign_Extract\`
    )
    SELECT (SELECT COUNT(*) FROM ebucks) AS ebucks_customers,
           (SELECT COUNT(*) FROM poc)    AS poc_customers,
           (SELECT COUNT(DISTINCT e.cust_id_reg_no) FROM ebucks e
            INNER JOIN poc p USING (cust_id_reg_no)) AS overlap
"


# ── 9. If LR_POC has an email column, try the full 3-way join ─────────
hdr "9. Try the full chain: FRG.email -> LR_POC.email -> eBucks via cust_id_reg_no"
echo "If this returns real numbers, we have the eBucks reward_seg_id mapped to FRG."
bq_prod "
    WITH poc AS (
        SELECT DISTINCT mobile, cust_id_reg_no
        FROM \`$PROD.PicknPay.LiveRamp_POC_Campaign_Extract\`
        WHERE mobile IS NOT NULL AND cust_id_reg_no IS NOT NULL
    ),
    ebucks AS (
        SELECT DISTINCT cust_id_reg_no, reward_seg_id
        FROM \`$PROD.PicknPay.PNP_eBucks_BurgerFriday\`
    ),
    frg AS (
        SELECT DISTINCT EMAIL_ADDR, CUST_CELL_NO
        FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
    )
    SELECT
        (SELECT COUNT(*) FROM frg)    AS frg_n,
        (SELECT COUNT(*) FROM poc)    AS poc_n,
        (SELECT COUNT(*) FROM ebucks) AS ebucks_n,
        (SELECT COUNT(DISTINCT f.EMAIL_ADDR)
         FROM frg f
         INNER JOIN poc p ON CAST(f.CUST_CELL_NO AS STRING) = CAST(p.mobile AS STRING)
         INNER JOIN ebucks e USING (cust_id_reg_no)) AS three_way_join
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Priority reads:"
echo "    Section 4: is latest_fnb_trns_base the bridge?"
echo "    Section 6+7: what are the eBucks reward tiers we can quote?"
echo "    Section 8: does eBucks x LR_POC overlap? (bridge validation)"
echo "    Section 9: does the 3-way join work? (payoff)"
echo "════════════════════════════════════════════════════════════"
