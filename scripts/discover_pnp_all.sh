#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# ONE script that does everything needed for the Tuesday PnP unlock deck.
#
# Combines:
#   - LR mirror inventory + schemas + samples
#   - Cross-source verification of PnP slide claims vs our FRG data
#   - Full sweep of every prod dataset for loyalty/reward/partner signal
#   - Hunt for the missing eBucks x SmartShopper LR output
#   - Join-key discovery: FRG x every LR audience overlap counts
#   - Segment mix INSIDE each LR audience (the killer deck stats)
#
# Read-only everywhere. Screenshot-friendly output (compact tables).
#
# Usage:
#   bash scripts/discover_pnp_all.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired, re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired, re-logging in..."
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


hdr "PnP UNLOCK DECK, one-shot discovery"


# ═════════════════════════════════════════════════════════════════════
# PART A: DATASET INVENTORY (what we have to work with)
# ═════════════════════════════════════════════════════════════════════

hdr "A1. Every prod dataset with table count"
for ds in Adidas ETL_DEV Metropolitan PicknPay demographics_customer \
          demographics_fld demographics_mb staging; do
    tables=$(bq --project_id="$PROD" --location=africa-south1 \
        ls --max_results=200 "$PROD:$ds" 2>/dev/null | tail -n +3 | wc -l | tr -d ' ')
    echo "  $ds: $tables tables"
done


hdr "A2. Prod PicknPay tables + row counts"
bq_prod "
    SELECT t.table_name,
           (SELECT SUM(total_rows) FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.PARTITIONS\` p
            WHERE p.table_name = t.table_name) AS rows
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.TABLES\` t
    WHERE table_type = 'BASE TABLE'
    ORDER BY rows DESC NULLS LAST
"


hdr "A3. LR mirrors in sandbox (pnp_liveramp) + row counts"
bq_sb "
    SELECT t.table_name,
           (SELECT SUM(total_rows) FROM \`$SB.pnp_liveramp.INFORMATION_SCHEMA.PARTITIONS\` p
            WHERE p.table_name = t.table_name) AS rows
    FROM \`$SB.pnp_liveramp.INFORMATION_SCHEMA.TABLES\` t
    WHERE table_type = 'BASE TABLE'
    ORDER BY rows DESC NULLS LAST
"


# ═════════════════════════════════════════════════════════════════════
# PART B: VERIFY PNP SLIDE CLAIMS AGAINST OUR DATA
# ═════════════════════════════════════════════════════════════════════

hdr "B1. VERIFY: PnP slide 5 pyramid (13.6/21.5/22.5/41.9) vs our FRG buckets"
bq_prod "
    WITH bucketed AS (
        SELECT CASE
            WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL       THEN '4. Lapsed proxy: no PnP spend'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.10 THEN '3. Tertiary proxy: <10%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.30 THEN '2. Secondary proxy: 10-30%'
            ELSE                                                     '1. Primary proxy: 30%+'
        END AS pnp_bucket
        FROM $FRG
        WHERE val_tot_trns > 0
    )
    SELECT pnp_bucket,
           COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct_of_frg
    FROM bucketed
    GROUP BY pnp_bucket
    ORDER BY pnp_bucket
"


hdr "B2. VERIFY: FRG reach vs PnP 20.6M/9M SS base"
bq_prod "
    SELECT COUNT(*)                    AS frg_customers,
           COUNTIF(nr_pnp_trns > 0)    AS pnp_active_in_frg,
           ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1) AS pct_active
    FROM $FRG
"


# ═════════════════════════════════════════════════════════════════════
# PART C: FRG CROSS-TABS (proves segment-level story)
# ═════════════════════════════════════════════════════════════════════

hdr "C1. Retail_Model x PnP (who spends most, wallet share)"
bq_prod "
    SELECT Retail_Model,
           COUNT(*) AS customers,
           COUNTIF(nr_pnp_trns > 0) AS pnp_active,
           ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1) AS active_pct,
           ROUND(AVG(val_pnp_trns), 0) AS avg_pnp_spend,
           ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_wallet_pct,
           ROUND(SUM(val_pnp_trns) / 1e6, 1) AS total_pnp_spend_m
    FROM $FRG
    WHERE val_tot_trns > 0
    GROUP BY Retail_Model
    ORDER BY total_pnp_spend_m DESC
"


hdr "C2. Wallet-share buckets, the headroom slide"
bq_prod "
    WITH bucketed AS (
        SELECT CASE
            WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL       THEN '0. No PnP spend'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.05 THEN '1. Under 5%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.10 THEN '2. 5-10%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.20 THEN '3. 10-20%'
            WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.40 THEN '4. 20-40%'
            ELSE                                                     '5. 40%+'
        END AS bucket,
        val_pnp_trns, val_tot_trns
        FROM $FRG WHERE val_tot_trns > 0
    )
    SELECT bucket,
           COUNT(*) AS customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
           ROUND(SUM(val_pnp_trns) / 1e6, 1) AS pnp_spend_m,
           ROUND(SUM(val_tot_trns) / 1e6, 1) AS total_spend_m
    FROM bucketed GROUP BY bucket ORDER BY bucket
"


hdr "C3. Grocery-delivery adoption (ASAP relevance) by Retail_Model"
bq_prod "
    SELECT Retail_Model,
           COUNT(*) AS customers,
           COUNTIF(grocery_delivery_trns > 0) AS delivery_users,
           ROUND(100.0 * COUNTIF(grocery_delivery_trns > 0) / COUNT(*), 1) AS adoption_pct
    FROM $FRG
    GROUP BY Retail_Model
    ORDER BY adoption_pct DESC
"


# ═════════════════════════════════════════════════════════════════════
# PART D: HUNT FOR MISSING EBUCKS x SMARTSHOPPER DATA
# ═════════════════════════════════════════════════════════════════════

hdr "D1. Every GCS bucket you can see"
gcloud storage buckets list --format='value(name,location)' 2>/dev/null | head -30


hdr "D2. GCS objects mentioning ebucks/smart/payday/burger across all buckets"
for b in $(gcloud storage buckets list --format='value(name)' 2>/dev/null); do
    hits=$(gcloud storage ls --recursive "gs://${b}/**" 2>/dev/null \
        | grep -iE 'ebucks|smartshopper|smart_shopper|payday_ebucks|burger' \
        | head -3)
    if [ -n "$hits" ]; then
        echo
        echo "  gs://$b:"
        echo "$hits" | sed 's/^/    /'
    fi
done


hdr "D3. Prod PicknPay tables/columns mentioning ebucks/smart/reward/loyalty"
bq_prod "
    SELECT DISTINCT table_name
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    WHERE LOWER(table_name) LIKE '%ebucks%'
       OR LOWER(table_name) LIKE '%smart%'
       OR LOWER(table_name) LIKE '%reward%'
       OR LOWER(column_name) LIKE '%ebucks%'
       OR LOWER(column_name) LIKE '%smart%'
       OR LOWER(column_name) LIKE '%reward%'
       OR LOWER(column_name) LIKE '%loyalty%'
    ORDER BY table_name
"


# ═════════════════════════════════════════════════════════════════════
# PART E: JOIN-KEY DISCOVERY (FRG x LR audiences)
# ═════════════════════════════════════════════════════════════════════

hdr "E1. Confirm FRG EMAIL_ADDR is SHA-256"
bq_prod "
    SELECT LENGTH(EMAIL_ADDR) AS len,
           REGEXP_CONTAINS(EMAIL_ADDR, r'^[0-9a-f]{64}\$') AS is_sha256,
           COUNT(*) AS n
    FROM $FRG WHERE EMAIL_ADDR IS NOT NULL
    GROUP BY len, is_sha256
    ORDER BY n DESC LIMIT 5
"


hdr "E2. lr_out_pnp_audiences_for_awareness (2.28M) x FRG (2.29M) overlap"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT string_field_0 AS email
        FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\`
    )
    SELECT (SELECT COUNT(DISTINCT EMAIL_ADDR) FROM $FRG) AS frg,
           (SELECT COUNT(*) FROM lr) AS lr_audience,
           (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
            JOIN lr l ON f.EMAIL_ADDR = l.email) AS overlap
"


hdr "E3. lr_out_pnp_clothing_base (857k) x FRG with SmartShopper flag"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    )
    SELECT COUNT(*) AS clothing_total,
           COUNTIF(SmartShopper_Indicator = 'Y') AS with_ss,
           COUNTIF(SmartShopper_Indicator = 'N') AS without_ss,
           (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
            JOIN lr l ON f.EMAIL_ADDR = l.email_addr) AS overlap_with_frg
    FROM lr
"


hdr "E4. lr_out_ntb_transact (788k, baby NTB) x FRG"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT EMAIL AS email FROM \`$SB.pnp_liveramp.lr_out_ntb_transact\`
    )
    SELECT (SELECT COUNT(*) FROM lr) AS ntb_total,
           (SELECT COUNT(DISTINCT f.EMAIL_ADDR) FROM $FRG f
            JOIN lr l ON f.EMAIL_ADDR = l.email) AS overlap_with_frg
"


# ═════════════════════════════════════════════════════════════════════
# PART F: THE KILLER STATS (segment mix INSIDE LR audiences)
# ═════════════════════════════════════════════════════════════════════

hdr "F1. FRG Retail_Model mix INSIDE lr_out_pnp_audiences_for_awareness"
echo "For the audience PnP asked us to target, WHO are they across FNB tiers?"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT string_field_0 AS email
        FROM \`$SB.pnp_liveramp.lr_out_pnp_audiences_for_awareness\`
    )
    SELECT f.Retail_Model,
           COUNT(*) AS matched_customers,
           ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1) AS pct,
           ROUND(AVG(f.val_pnp_trns), 0) AS avg_pnp_spend,
           ROUND(AVG(SAFE_DIVIDE(f.val_pnp_trns, f.val_tot_trns)) * 100, 1) AS wallet_pct
    FROM $FRG f
    JOIN lr l ON f.EMAIL_ADDR = l.email
    WHERE f.val_tot_trns > 0
    GROUP BY f.Retail_Model
    ORDER BY matched_customers DESC
"


hdr "F2. FRG mix INSIDE lr_out_pnp_clothing_base, split by SmartShopper Y/N"
bq_prod "
    WITH lr AS (
        SELECT DISTINCT email_addr, SmartShopper_Indicator
        FROM \`$SB.pnp_liveramp.lr_out_pnp_clothing_base\`
    )
    SELECT f.Retail_Model,
           l.SmartShopper_Indicator,
           COUNT(*) AS matched
    FROM $FRG f
    JOIN lr l ON f.EMAIL_ADDR = l.email_addr
    GROUP BY f.Retail_Model, l.SmartShopper_Indicator
    ORDER BY matched DESC LIMIT 20
"


hdr "F3. Baby NTB propensity by FRG Retail_Model (the untapped baby-category story)"
bq_prod "
    WITH lr AS (
        SELECT EMAIL AS email, avg_monthly_baby_spend, avg_frequency_3m
        FROM \`$SB.pnp_liveramp.lr_out_ntb_transact\`
    )
    SELECT f.Retail_Model,
           COUNT(*) AS customers,
           ROUND(AVG(l.avg_monthly_baby_spend), 0) AS avg_baby_spend,
           ROUND(AVG(l.avg_frequency_3m), 1) AS avg_freq_3m
    FROM $FRG f
    JOIN lr l ON f.EMAIL_ADDR = l.email
    GROUP BY f.Retail_Model
    ORDER BY avg_baby_spend DESC
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Everything in one screenshot-per-section."
echo "  Screenshot each Part (A-F) and I'll build the two decks:"
echo "    - Requested (Marina): slides 9 + 12"
echo "    - Super deck: every unlock we can defend"
echo "════════════════════════════════════════════════════════════"
