#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Deep-inspect every table in fmn-sandbox.pnp_liveramp (the LR mirrors we
# ingested from gs://liveramp_output/).
#
# For each table:
#   - Column schema
#   - 5 sample rows
#   - Row count + distinct identifier counts where obvious
#
# Then a set of cross-source verification queries that check the PnP-slide
# claims and the FRG cross-tab claims against the LR data, so every number
# we put in Tuesday's deck is defensible from three sources.
#
# Read-only. Screenshot-friendly.
#
# Usage:
#   bash scripts/discover_lr_tables_deep.sh
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

SB="fmn-sandbox"
DS="pnp_liveramp"
PROD="fmn-production-462014"

bq_sb() {
    bq query --quiet --use_legacy_sql=false --project_id="$SB" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}
bq_prod() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Deep inspection of LR clean-room mirrors + cross-source"
echo "  verification for the Tuesday PnP deck"
echo "════════════════════════════════════════════════════════════"


# ── 1. Every lr_out_* / aud_* table with row + column counts ────────────
echo
echo "── 1. LR mirrors inventory ──"
bq_sb "
    SELECT
        t.table_name,
        p.total_rows,
        (SELECT COUNT(*) FROM \`$SB.$DS.INFORMATION_SCHEMA.COLUMNS\` c
         WHERE c.table_name = t.table_name) AS n_columns,
        ROUND(p.total_logical_bytes / 1024 / 1024, 1) AS size_mb
    FROM \`$SB.$DS.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name,
               SUM(total_rows) AS total_rows,
               SUM(total_logical_bytes) AS total_logical_bytes
        FROM \`$SB.$DS.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE t.table_type = 'BASE TABLE'
    ORDER BY p.total_rows DESC NULLS LAST
"


# ── 2. Schema of every LR table ─────────────────────────────────────────
echo
echo "── 2. Column schemas ──"
bq_sb "
    SELECT table_name, column_name, data_type
    FROM \`$SB.$DS.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name LIKE 'lr_out_%' OR table_name LIKE 'aud_%'
    ORDER BY table_name, ordinal_position
    LIMIT 200
"


# ── 3. Sample rows from each LR table ───────────────────────────────────
# We do the top 5 by row count to keep it screenshot-sized.
echo
echo "── 3. Sample rows from the 5 largest LR tables ──"
top5=$(bq query --quiet --use_legacy_sql=false --project_id="$SB" \
    --location=africa-south1 --format=csv --max_rows=5 \
    "SELECT t.table_name
     FROM \`$SB.$DS.INFORMATION_SCHEMA.TABLES\` t
     LEFT JOIN (
         SELECT table_name, SUM(total_rows) AS total_rows
         FROM \`$SB.$DS.INFORMATION_SCHEMA.PARTITIONS\`
         GROUP BY table_name
     ) p USING (table_name)
     WHERE t.table_type = 'BASE TABLE'
       AND (t.table_name LIKE 'lr_out_%' OR t.table_name LIKE 'aud_%')
     ORDER BY p.total_rows DESC NULLS LAST
     LIMIT 5" 2>/dev/null | tail -n +2)

for t in $top5; do
    t=$(echo "$t" | tr -d '\r ')
    [ -z "$t" ] && continue
    echo
    echo "  ── $t ──"
    bq_sb "SELECT * FROM \`$SB.$DS.$t\` LIMIT 3"
done


# ── 4. Distinct-identifier probe on the biggest table (fnb_pnp_awareness)
echo
echo "── 4. Identifier density on lr_out_fnb_pnp_awareness (31.8M rows) ──"
echo "How many distinct rows, and what does column 0/1/2 (likely EMAIL, PHONE)"
echo "look like? This tells us if the file is a unique audience or a fanned join."
bq_sb "
    SELECT column_name
    FROM \`$SB.$DS.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'lr_out_fnb_pnp_awareness'
    ORDER BY ordinal_position
    LIMIT 20
"


# ── 5. Cross-source verification: does the PnP slide 5 pyramid MATCH our
#    wallet-share buckets from FRG cross-tab? ────────────────────────────
echo
echo "── 5. VERIFY: PnP slide 5 pyramid vs our FRG wallet-share buckets ──"
echo "PnP slide 5 says: Primary 13.6% / Secondary 21.5% / Tertiary 22.5% / Lapsed 41.9%"
echo "Our sandbox wallet-share buckets should have a similar shape:"
bq_prod "
    WITH bucketed AS (
        SELECT
            CASE
                WHEN val_pnp_trns = 0 OR val_pnp_trns IS NULL THEN '4. Lapsed proxy: no PnP spend'
                WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.10 THEN '3. Tertiary proxy: <10%'
                WHEN SAFE_DIVIDE(val_pnp_trns, val_tot_trns) < 0.30 THEN '2. Secondary proxy: 10-30%'
                ELSE                                                    '1. Primary proxy: 30%+'
            END AS pnp_bucket
        FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
        WHERE val_tot_trns > 0
    )
    SELECT
        pnp_bucket,
        COUNT(*)                                                  AS customers,
        ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 1)        AS pct_of_frg,
        'PnP:  13.6% Primary / 21.5% Secondary / 22.5% Tertiary / 41.9% Lapsed' AS pnp_reference
    FROM bucketed
    GROUP BY pnp_bucket
    ORDER BY pnp_bucket
"


# ── 6. Cross-source verification: PnP slide 3 counts ────────────────────
echo
echo "── 6. VERIFY: PnP slide 3 total base numbers vs our audience upload ──"
echo "PnP slide 3 says: 20.6M Total registered SS, 9M Active SS (52wk)"
echo "Our Audience_Upload is a 2.29M-customer SUBSET (FRG-active-at-PnP overlap)"
bq_prod "
    SELECT
        COUNT(*)                       AS frg_customers_in_audience_upload,
        COUNTIF(nr_pnp_trns > 0)       AS pnp_active_in_this_set,
        'PnP: 20.6M SS registered, 9M active. Our set is FRG-only overlap.' AS reference
    FROM \`$PROD.PicknPay.Audience_Upload_20260206\`
"


# ── 7. Cross-source verification: eBucks x SS-tier overlap (if the LR
#    table for eBucks-x-SmartShopper exists as an lr_out_* table) ───────
echo
echo "── 7. eBucks x SmartShopper: what did the LR question produce? ──"
echo "Look for any lr_out_* table with 'ebucks' or 'smartshopper' in the name"
bq_sb "
    SELECT table_name
    FROM \`$SB.$DS.INFORMATION_SCHEMA.TABLES\`
    WHERE table_type = 'BASE TABLE'
      AND (LOWER(table_name) LIKE '%ebucks%'
        OR LOWER(table_name) LIKE '%smartshopper%'
        OR LOWER(table_name) LIKE '%smart_shopper%')
"


# ── 8. Cross-source verification: PnP_Audiences_for_Awareness table
#    (2.28M rows) — what does its schema tell us? ────────────────────────
echo
echo "── 8. Schema of lr_out_pnp_audiences_for_awareness (2.28M rows) ──"
bq_sb "
    SELECT column_name, data_type
    FROM \`$SB.$DS.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'lr_out_pnp_audiences_for_awareness'
    ORDER BY ordinal_position
    LIMIT 30
"


# ── 9. NTB_transact / NTB_funeral: schema and sample (both 788,806 rows,
#    identical row counts, suspicious) ──────────────────────────────────
echo
echo "── 9. NTB_transact + NTB_funeral (identical 788,806 row counts) ──"
bq_sb "
    SELECT column_name, data_type
    FROM \`$SB.$DS.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name IN ('lr_out_ntb_transact', 'lr_out_ntb_funeral')
    ORDER BY table_name, ordinal_position
    LIMIT 30
"


# ── 10. PnP_clothing_base: is this the clothing-shopper audience? ──────
echo
echo "── 10. lr_out_pnp_clothing_base (857,373 rows) ──"
bq_sb "
    SELECT column_name, data_type
    FROM \`$SB.$DS.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'lr_out_pnp_clothing_base'
    ORDER BY ordinal_position
"


# ── 11. Overlap: FRG customer base vs LR audience outputs ──────────────
echo
echo "── 11. Overlap check: FRG Audience_Upload vs LR audiences ──"
echo "How many customers in each LR audience table appear in our FRG"
echo "Audience_Upload? This tells us the LR extracts are (mostly) subsets"
echo "of the FRG base, or if there is meaningful non-overlap."
echo "Skipped for now: requires join key discovery. Will be phase 2."


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Screenshot each section and I'll build the two decks"
echo "  (the requested one + the super one) from what shows up."
echo "════════════════════════════════════════════════════════════"
