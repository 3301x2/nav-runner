#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Cross-tab discovery for the PnP audience deck.
#
# Runs a matrix of segment-by-spend queries so we know which combinations
# of Retail_Model / MBD_Tier / Hypersegment / KPI_Risk_Class have the
# strongest PnP relationship and biggest headroom.
#
# All queries hit fmn-production-462014.PicknPay.Audience_Upload_20260206
# in place. Read-only. Screenshot-friendly output.
#
# Sections:
#   1. Retail_Model x PnP metrics (spend, wallet share, active pct)
#   2. MBD_Tier x PnP metrics
#   3. Hypersegment x PnP metrics (with case normalization)
#   4. KPI_Risk_Class x PnP metrics
#   5. Retail_Model x Hypersegment matrix (top cells by customers)
#   6. Retail_Model x MBD_Tier matrix
#   7. Wallet-share buckets: how many customers spend 0%, 1-10%, 10-30%,
#      30-50%, 50%+ of their basket at PnP (the growth-headroom slide)
#   8. Grocery delivery adoption by Retail_Model
#      (ASAP-relevant behavioural cut)
#
# Usage:
#   bash scripts/discover_pnp_cross_tabs.sh
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
TBL="\`$PROD.PicknPay.Audience_Upload_20260206\`"

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  PnP audience cross-tab discovery"
echo "  Base: $PROD.PicknPay.Audience_Upload_20260206"
echo "  (2.29M FRG customers, 1.34M PnP-active)"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Retail_Model x PnP metrics ──"
echo "(who spends most at PnP, and what share of their total wallet)"
bq_q "
    SELECT
        Retail_Model,
        COUNT(*)                                                     AS customers,
        COUNTIF(nr_pnp_trns > 0)                                     AS pnp_active,
        ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1)        AS pnp_active_pct,
        ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
        ROUND(AVG(val_tot_trns), 0)                                  AS avg_total_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_pnp_wallet_share_pct,
        ROUND(SUM(val_pnp_trns) / 1e6, 1)                            AS total_pnp_spend_m
    FROM $TBL
    WHERE val_tot_trns > 0
    GROUP BY Retail_Model
    ORDER BY total_pnp_spend_m DESC
"


echo
echo "── 2. MBD_Tier x PnP metrics ──"
bq_q "
    SELECT
        MBD_Tier,
        COUNT(*)                                                     AS customers,
        COUNTIF(nr_pnp_trns > 0)                                     AS pnp_active,
        ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1)        AS pnp_active_pct,
        ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_pnp_wallet_share_pct,
        ROUND(SUM(val_pnp_trns) / 1e6, 1)                            AS total_pnp_spend_m
    FROM $TBL
    WHERE val_tot_trns > 0
    GROUP BY MBD_Tier
    ORDER BY MBD_Tier
"


echo
echo "── 3. Hypersegment x PnP metrics (case-normalized) ──"
bq_q "
    SELECT
        REGEXP_REPLACE(
            INITCAP(Hypersegment),
            r'^([A-Z])\\. ', r'\\1. '
        )                                                             AS hypersegment_clean,
        COUNT(*)                                                     AS customers,
        COUNTIF(nr_pnp_trns > 0)                                     AS pnp_active,
        ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1)        AS pnp_active_pct,
        ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_pnp_wallet_share_pct,
        ROUND(SUM(val_pnp_trns) / 1e6, 1)                            AS total_pnp_spend_m
    FROM $TBL
    WHERE val_tot_trns > 0
    GROUP BY hypersegment_clean
    ORDER BY total_pnp_spend_m DESC
"


echo
echo "── 4. KPI_Risk_Class x PnP metrics ──"
bq_q "
    SELECT
        KPI_Risk_Class,
        COUNT(*)                                                     AS customers,
        COUNTIF(nr_pnp_trns > 0)                                     AS pnp_active,
        ROUND(100.0 * COUNTIF(nr_pnp_trns > 0) / COUNT(*), 1)        AS pnp_active_pct,
        ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS avg_pnp_wallet_share_pct,
        ROUND(SUM(val_pnp_trns) / 1e6, 1)                            AS total_pnp_spend_m
    FROM $TBL
    WHERE val_tot_trns > 0
    GROUP BY KPI_Risk_Class
    ORDER BY total_pnp_spend_m DESC
"


echo
echo "── 5. Retail_Model x Hypersegment matrix (top 20 cells by customers) ──"
bq_q "
    SELECT
        Retail_Model,
        UPPER(Hypersegment)                                          AS hypersegment,
        COUNT(*)                                                     AS customers,
        ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS wallet_share_pct
    FROM $TBL
    WHERE val_tot_trns > 0
    GROUP BY Retail_Model, hypersegment
    ORDER BY customers DESC
    LIMIT 20
"


echo
echo "── 6. Retail_Model x MBD_Tier matrix (top 20 cells) ──"
bq_q "
    SELECT
        Retail_Model,
        MBD_Tier,
        COUNT(*)                                                     AS customers,
        ROUND(AVG(val_pnp_trns), 0)                                  AS avg_pnp_spend,
        ROUND(AVG(SAFE_DIVIDE(val_pnp_trns, val_tot_trns)) * 100, 1) AS wallet_share_pct
    FROM $TBL
    WHERE val_tot_trns > 0
    GROUP BY Retail_Model, MBD_Tier
    ORDER BY customers DESC
    LIMIT 20
"


echo
echo "── 7. Wallet-share buckets ──"
echo "(the headroom slide: how much of the audience gives PnP < 10% of basket)"
bq_q "
    WITH bucketed AS (
        SELECT
            CASE
                WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL THEN '0. No PnP spend'
                WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.05 THEN '1. Under 5%'
                WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.10 THEN '2. 5-10%'
                WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.20 THEN '3. 10-20%'
                WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.40 THEN '4. 20-40%'
                ELSE '5. 40%+'
            END AS wallet_bucket,
            val_pnp_trns,
            val_tot_trns
        FROM $TBL
        WHERE val_tot_trns > 0
    )
    SELECT
        wallet_bucket,
        COUNT(*)                                                  AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct_of_audience,
        ROUND(SUM(val_pnp_trns) / 1e6, 1)                         AS pnp_spend_in_bucket_m,
        ROUND(SUM(val_tot_trns) / 1e6, 1)                         AS total_spend_in_bucket_m,
        ROUND(100.0 * SUM(val_pnp_trns) / SUM(val_tot_trns), 1)   AS bucket_avg_wallet_share
    FROM bucketed
    GROUP BY wallet_bucket
    ORDER BY wallet_bucket
"


echo
echo "── 8. Grocery-delivery adoption by Retail_Model ──"
echo "(ASAP-relevant: are the affluent tiers actually using online grocery?)"
bq_q "
    SELECT
        Retail_Model,
        COUNT(*)                                                     AS customers,
        COUNTIF(grocery_delivery_trns > 0)                           AS delivery_users,
        ROUND(100.0 * COUNTIF(grocery_delivery_trns > 0) / COUNT(*), 1) AS delivery_adoption_pct,
        ROUND(AVG(NULLIF(grocery_delivery_trns, 0)), 1)              AS avg_delivery_visits_when_active
    FROM $TBL
    GROUP BY Retail_Model
    ORDER BY delivery_adoption_pct DESC
"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Screenshot the sections and I'll turn them into the"
echo "  segment-by-segment story for the Tuesday deck (slide 12)."
echo "════════════════════════════════════════════════════════════"
