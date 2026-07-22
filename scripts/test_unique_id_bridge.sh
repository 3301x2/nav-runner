#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Test the hypothesis: FRG.UNIQUE_ID == eBucks.cust_id_reg_no.
#
# Both are FNB customer identifiers. If they're the same, we join direct
# and can attribute PnP behaviour by eBucks reward tier immediately.
#
# Read-only.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

LOG="$HOME/unique_id_bridge.log"
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
FRG="\`$PROD.PicknPay.Audience_Upload_20260206\`"
EBUCKS="\`$PROD.PicknPay.PNP_eBucks_BurgerFriday\`"

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

hdr "UNIQUE_ID vs cust_id_reg_no bridge test"


hdr "1. Sample 5 UNIQUE_ID from FRG"
bq_prod "SELECT UNIQUE_ID FROM $FRG WHERE UNIQUE_ID IS NOT NULL LIMIT 5"


hdr "2. Sample 5 cust_id_reg_no from eBucks BurgerFriday"
bq_prod "SELECT cust_id_reg_no FROM $EBUCKS WHERE cust_id_reg_no IS NOT NULL LIMIT 5"


hdr "3. Format check: what do these IDs look like?"
bq_prod "
    SELECT
        LENGTH(UNIQUE_ID) AS len,
        REGEXP_CONTAINS(UNIQUE_ID, r'^[0-9]+\$')            AS is_all_digits,
        REGEXP_CONTAINS(UNIQUE_ID, r'^[0-9a-f]{64}\$')      AS is_sha256,
        REGEXP_CONTAINS(UNIQUE_ID, r'^[0-9a-zA-Z]+\$')      AS is_alnum,
        COUNT(*) AS n
    FROM $FRG WHERE UNIQUE_ID IS NOT NULL
    GROUP BY len, is_all_digits, is_sha256, is_alnum
    ORDER BY n DESC LIMIT 5
"

bq_prod "
    SELECT
        LENGTH(cust_id_reg_no) AS len,
        REGEXP_CONTAINS(cust_id_reg_no, r'^[0-9]+\$')            AS is_all_digits,
        REGEXP_CONTAINS(cust_id_reg_no, r'^[0-9a-f]{64}\$')      AS is_sha256,
        REGEXP_CONTAINS(cust_id_reg_no, r'^[0-9a-zA-Z]+\$')      AS is_alnum,
        COUNT(*) AS n
    FROM $EBUCKS WHERE cust_id_reg_no IS NOT NULL
    GROUP BY len, is_all_digits, is_sha256, is_alnum
    ORDER BY n DESC LIMIT 5
"


hdr "4. THE TEST: direct UNIQUE_ID = cust_id_reg_no overlap"
bq_prod "
    WITH frg AS (
        SELECT DISTINCT UNIQUE_ID AS id FROM $FRG WHERE UNIQUE_ID IS NOT NULL
    ),
    eb AS (
        SELECT DISTINCT cust_id_reg_no AS id FROM $EBUCKS WHERE cust_id_reg_no IS NOT NULL
    )
    SELECT
        (SELECT COUNT(*) FROM frg) AS frg_ids,
        (SELECT COUNT(*) FROM eb)  AS ebucks_ids,
        (SELECT COUNT(*) FROM frg INNER JOIN eb USING (id)) AS overlap,
        ROUND(100.0 * (SELECT COUNT(*) FROM frg INNER JOIN eb USING (id))
              / (SELECT COUNT(*) FROM frg), 1) AS pct_of_frg,
        ROUND(100.0 * (SELECT COUNT(*) FROM frg INNER JOIN eb USING (id))
              / (SELECT COUNT(*) FROM eb), 1) AS pct_of_ebucks
"


hdr "5. IF JOIN WORKS: FRG Retail_Model x eBucks reward tier"
echo "This is deck-worthy: how do FNB Retail_Model tiers map to eBucks tiers?"
bq_prod "
    WITH eb AS (
        SELECT DISTINCT cust_id_reg_no AS id, reward_seg_id FROM $EBUCKS
    )
    SELECT f.Retail_Model,
           eb.reward_seg_id,
           COUNT(*) AS customers,
           ROUND(AVG(f.val_pnp_trns), 0) AS avg_pnp_spend,
           ROUND(AVG(SAFE_DIVIDE(f.val_pnp_trns, f.val_tot_trns)) * 100, 1) AS wallet_pct
    FROM $FRG f
    INNER JOIN eb ON f.UNIQUE_ID = eb.id
    WHERE f.val_tot_trns > 0
    GROUP BY f.Retail_Model, eb.reward_seg_id
    ORDER BY customers DESC
    LIMIT 25
"


hdr "6. IF JOIN WORKS: PnP wallet share and spend by eBucks reward tier alone"
echo "The killer stat: does higher eBucks tier = higher PnP wallet share?"
bq_prod "
    WITH eb AS (
        SELECT DISTINCT cust_id_reg_no AS id, reward_seg_id FROM $EBUCKS
    )
    SELECT eb.reward_seg_id,
           COUNT(*) AS customers,
           COUNTIF(f.nr_pnp_trns > 0) AS pnp_active,
           ROUND(100.0 * COUNTIF(f.nr_pnp_trns > 0) / COUNT(*), 1) AS active_pct,
           ROUND(AVG(f.val_pnp_trns), 0) AS avg_pnp_spend,
           ROUND(AVG(SAFE_DIVIDE(f.val_pnp_trns, f.val_tot_trns)) * 100, 1) AS wallet_pct,
           ROUND(SUM(f.val_pnp_trns) / 1e6, 1) AS total_pnp_m
    FROM $FRG f
    INNER JOIN eb ON f.UNIQUE_ID = eb.id
    WHERE f.val_tot_trns > 0
    GROUP BY eb.reward_seg_id
    ORDER BY total_pnp_m DESC
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. If Section 4 shows a real overlap (>50%), we have"
echo "  the bridge and Sections 5+6 are the deck stats we needed."
echo "════════════════════════════════════════════════════════════"
