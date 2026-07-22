#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Join-key discovery: figure out which columns bridge FRG customers to
# every LR audience output.
#
# We know the FRG side has EMAIL_ADDR (SHA-256 hashed) and CUST_CELL_NO.
# We know each LR table has different column names for the same hashes:
#   - lr_out_fnb_pnp_awareness:      2 cols (unknown names, likely email+phone)
#   - lr_out_extract_20022026:       EMAIL_ADDR column visible
#   - lr_out_extract_18022026:       hem + mobile
#   - lr_out_pnp_audiences_for_awareness: string_field_0
#   - lr_out_pnp_clothing_base:      email_addr + SmartShopper_Indicator
#   - lr_out_ntb_transact/funeral:   EMAIL column
#   - aud_pnp_audience_upload:       EMAIL_ADDR + CUST_CELL_NO
#
# This script does the actual joins where we can, and reports the
# match counts. Every match gives us a defensible "X of Y" stat for
# the deck.
#
# Read-only.
#
# Usage:
#   bash scripts/discover_join_keys.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    gcloud auth application-default login
fi

PROD="fmn-production-462014"
SB="fmn-sandbox"
FRG="\`$PROD.PicknPay.Audience_Upload_20260206\`"

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Join-key discovery: FRG x every LR audience"
echo "════════════════════════════════════════════════════════════"


# ── 1. Confirm hash format on FRG side ────────────────────────────────
echo
echo "── 1. FRG EMAIL_ADDR format (Audience_Upload) ──"
echo "Check if EMAIL_ADDR is SHA-256 (64 hex chars) or raw"
bq_q "
    SELECT
        LENGTH(EMAIL_ADDR)                                            AS len_email,
        REGEXP_CONTAINS(EMAIL_ADDR, r'^[0-9a-f]{64}\$')                AS is_sha256,
        SUBSTR(EMAIL_ADDR, 1, 12)                                     AS sample_prefix,
        COUNT(*)                                                      AS n_rows
    FROM $FRG
    WHERE EMAIL_ADDR IS NOT NULL
    GROUP BY len_email, is_sha256, sample_prefix
    ORDER BY n_rows DESC
    LIMIT 5
"


# ── 2. lr_out_pnp_audiences_for_awareness overlap with FRG ────────────
echo
echo "── 2. lr_out_pnp_audiences_for_awareness (2.28M) x FRG (2.29M) ──"
echo "Does this LR audience overlap our FRG base?"
bq_q "
    WITH lr AS (
        SELECT DISTINCT string_field_0 AS email
        FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\`
    )
    SELECT
        (SELECT COUNT(DISTINCT EMAIL_ADDR) FROM $FRG)                              AS frg_distinct,
        (SELECT COUNT(*) FROM lr)                                                  AS lr_distinct,
        (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
         INNER JOIN lr l ON f.EMAIL_ADDR = l.email)                                AS overlap,
        ROUND(100.0 * (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
         INNER JOIN lr l ON f.EMAIL_ADDR = l.email)
              / NULLIF((SELECT COUNT(DISTINCT EMAIL_ADDR) FROM $FRG), 0), 1)       AS pct_of_frg
"


# ── 3. lr_out_pnp_clothing_base overlap with FRG ──────────────────────
echo
echo "── 3. lr_out_pnp_clothing_base (857k) x FRG (2.29M) ──"
echo "How many FRG customers are also PnP Clothing shoppers?"
echo "And what % of them are Smart Shopper members?"
bq_q "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    )
    SELECT
        (SELECT COUNT(*) FROM lr)                                        AS clothing_customers,
        COUNTIF(lr.SmartShopper_Indicator = 'Y')                         AS clothing_with_ss,
        COUNTIF(lr.SmartShopper_Indicator = 'N')                         AS clothing_without_ss,
        ROUND(100.0 * COUNTIF(lr.SmartShopper_Indicator = 'Y')
              / COUNT(*), 1)                                             AS pct_with_ss,
        (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
         INNER JOIN lr l ON f.EMAIL_ADDR = l.email_addr)                 AS overlap_with_frg
    FROM lr
"


# ── 4. lr_out_ntb_transact overlap: are these FRG or PnP customers? ──
echo
echo "── 4. lr_out_ntb_transact (788k, NTB baby scoring) x FRG (2.29M) ──"
bq_q "
    WITH lr AS (
        SELECT DISTINCT EMAIL AS email FROM \`$SB.pnp_liveramp.lr_out_ntb_transact\`
    )
    SELECT
        (SELECT COUNT(*) FROM lr)                                        AS ntb_transact_customers,
        (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
         INNER JOIN lr l ON f.EMAIL_ADDR = l.email)                      AS overlap_with_frg,
        ROUND(100.0 * (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
         INNER JOIN lr l ON f.EMAIL_ADDR = l.email)
              / (SELECT COUNT(*) FROM lr), 1)                            AS pct_frg
"


# ── 5. lr_out_extract_18022026 overlap ────────────────────────────────
echo
echo "── 5. lr_out_extract_18022026 (1.53M) x FRG (2.29M) ──"
bq_q "
    WITH lr AS (
        SELECT DISTINCT hem AS email FROM \`$SB.pnp_liveramp.lr_out_extract_18022026\`
    )
    SELECT
        (SELECT COUNT(*) FROM lr)                                        AS extract_customers,
        (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
         INNER JOIN lr l ON f.EMAIL_ADDR = l.email)                      AS overlap_with_frg
"


# ── 6. lr_out_fnb_pnp_awareness (31.8M rows, fanned) ──────────────────
echo
echo "── 6. lr_out_fnb_pnp_awareness (31.8M) — first check the columns ──"
bq bq query --quiet --use_legacy_sql=false --project_id="$SB" \
    --location=africa-south1 --format=pretty --max_rows=5 \
    "SELECT column_name, data_type FROM \`$SB.pnp_liveramp.INFORMATION_SCHEMA.COLUMNS\`
     WHERE table_name = 'lr_out_fnb_pnp_awareness'"
echo "  Then distinct email count:"
bq_q "
    SELECT COUNT(DISTINCT string_field_0) AS distinct_ids_col0,
           COUNT(*) AS total_rows
    FROM \`$SB.pnp_liveramp.lr_out_fnb_pnp_awareness\`
"


# ── 7. Segment-level LR overlap: for each LR audience, what does the
#    FRG segment mix look like inside? ────────────────────────────────
echo
echo "── 7. FRG segment mix INSIDE lr_out_pnp_audiences_for_awareness ──"
echo "This is THE killer stat: for the customers PnP already knows are"
echo "'awareness targets', how are they distributed across FNB tiers?"
bq_q "
    WITH lr AS (
        SELECT DISTINCT string_field_0 AS email
        FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\`
    ),
    matched AS (
        SELECT f.Retail_Model, f.MBD_Tier, f.KPI_Risk_Class
        FROM $FRG f
        INNER JOIN lr l ON f.EMAIL_ADDR = l.email
    )
    SELECT
        Retail_Model,
        COUNT(*)                                                     AS matched_customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)           AS pct
    FROM matched
    GROUP BY Retail_Model
    ORDER BY matched_customers DESC
"


# ── 8. Same for the clothing base ────────────────────────────────────
echo
echo "── 8. FRG segment mix INSIDE lr_out_pnp_clothing_base ──"
bq_q "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    ),
    matched AS (
        SELECT f.Retail_Model, f.MBD_Tier, l.SmartShopper_Indicator
        FROM $FRG f
        INNER JOIN lr l ON f.EMAIL_ADDR = l.email_addr
    )
    SELECT
        Retail_Model,
        SmartShopper_Indicator,
        COUNT(*)                                                     AS matched_customers
    FROM matched
    GROUP BY Retail_Model, SmartShopper_Indicator
    ORDER BY matched_customers DESC
    LIMIT 25
"


# ── 9. NTB baby propensity by FRG segment ───────────────────────────
echo
echo "── 9. NTB baby propensity by FRG segment ──"
echo "Which FRG wealth tiers have the strongest baby-category propensity?"
bq_q "
    WITH lr AS (
        SELECT EMAIL AS email,
               avg_monthly_baby_spend,
               avg_recency,
               avg_frequency_3m
        FROM \`$SB.pnp_liveramp.lr_out_ntb_transact\`
    ),
    matched AS (
        SELECT
            f.Retail_Model,
            l.avg_monthly_baby_spend,
            l.avg_frequency_3m
        FROM $FRG f
        INNER JOIN lr l ON f.EMAIL_ADDR = l.email
    )
    SELECT
        Retail_Model,
        COUNT(*)                                                     AS customers,
        ROUND(AVG(avg_monthly_baby_spend), 0)                        AS avg_baby_spend,
        ROUND(AVG(avg_frequency_3m), 1)                              AS avg_freq_3m
    FROM matched
    GROUP BY Retail_Model
    ORDER BY avg_baby_spend DESC
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Every match here gives us a defensible overlap stat"
echo "  for the deck. Sections 7, 8, 9 are the killers: they tell"
echo "  us exactly which FNB tiers to over-index each PnP audience"
echo "  play on."
echo "════════════════════════════════════════════════════════════"
