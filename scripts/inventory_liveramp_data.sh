#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Full inventory of the LiveRamp data visible from our GCP identity.
#
# Dumps EVERYTHING into ~/lr_inventory/ as text files so you don't have to
# read numbers off a screenshot. The terminal only prints a short summary.
#
# Outputs:
#   ~/lr_inventory/00_tables.txt          - PicknPay tables + row counts
#   ~/lr_inventory/01_schemas.txt         - All columns for every table
#   ~/lr_inventory/02_samples/<tbl>.txt   - 5 sample rows per table
#   ~/lr_inventory/03_lr_partitions.txt   - Every date partition in gs://liveramp_output
#   ~/lr_inventory/04_lr_all_files.txt    - Every file in gs://liveramp_output (full paths)
#   ~/lr_inventory/05_lr_file_types.txt   - Unique filename patterns
#   ~/lr_inventory/06_lr_previews/<f>.csv - Head of the 3 most recent CSV outputs
#   ~/lr_inventory/07_audience_uploads.txt - Contents of gs://picknpay_audience_uploads
#   ~/lr_inventory/08_summary.txt         - Everything summarised for the deck
#
# Read-only. Metadata + tiny sample reads. No writes to any BQ or GCS.
#
# Usage:
#   bash scripts/inventory_liveramp_data.sh
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
OUT="$HOME/lr_inventory"
mkdir -p "$OUT" "$OUT/02_samples" "$OUT/06_lr_previews"

bq_q_pretty() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=pretty --max_rows=500 "$1"
}
bq_q_csv() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=csv --max_rows=500 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  LiveRamp inventory. Writing to $OUT/"
echo "════════════════════════════════════════════════════════════"


# ── 1. PicknPay tables + row counts (via INFORMATION_SCHEMA, africa-south1 safe)
echo
echo "[1/8] PicknPay tables + row counts →  00_tables.txt"
bq_q_pretty "
    SELECT
        t.table_name,
        p.row_count,
        ROUND(p.total_logical_bytes / 1024 / 1024, 1) AS size_mb,
        t.creation_time,
        t.table_type
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name,
               SUM(row_count) AS row_count,
               SUM(total_logical_bytes) AS total_logical_bytes
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    ORDER BY t.creation_time DESC
" > "$OUT/00_tables.txt" 2>&1


# ── 2. Full schema of every table
echo "[2/8] Column schema for every table →  01_schemas.txt"
bq_q_pretty "
    SELECT
        table_name,
        column_name,
        data_type,
        ordinal_position
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.COLUMNS\`
    ORDER BY table_name, ordinal_position
" > "$OUT/01_schemas.txt" 2>&1


# ── 3. Sample rows from every table (top 5 by row count)
echo "[3/8] Sample rows from top 5 tables →  02_samples/<table>.txt"
# Use the raw table list from INFORMATION_SCHEMA (no reliance on __TABLES__)
top_tables_csv=$(bq_q_csv "
    SELECT t.table_name
    FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.TABLES\` t
    LEFT JOIN (
        SELECT table_name, SUM(row_count) AS row_count
        FROM \`$PROD.PicknPay.INFORMATION_SCHEMA.PARTITIONS\`
        GROUP BY table_name
    ) p USING (table_name)
    WHERE t.table_type = 'BASE TABLE'
    ORDER BY p.row_count DESC NULLS LAST
    LIMIT 5
" 2>/dev/null | tail -n +2)

while IFS= read -r t; do
    [ -z "$t" ] && continue
    # Clean quotes/whitespace defensively
    tclean=$(echo "$t" | tr -d '"' | tr -d ' ')
    [ -z "$tclean" ] && continue
    echo "    ... sampling $tclean"
    bq_q_pretty "SELECT * FROM \`$PROD.PicknPay.$tclean\` LIMIT 5" \
        > "$OUT/02_samples/${tclean}.txt" 2>&1
done <<< "$top_tables_csv"


# ── 4. All date partitions in gs://liveramp_output/
echo "[4/8] LR output date partitions →  03_lr_partitions.txt"
gcloud storage ls "gs://liveramp_output/" 2>/dev/null | sort -u > "$OUT/03_lr_partitions.txt"


# ── 5. Every file in gs://liveramp_output/ (full recursive listing)
echo "[5/8] All LR output files →  04_lr_all_files.txt (this can take a minute)"
gcloud storage ls --recursive "gs://liveramp_output/**" 2>/dev/null \
    | grep -E '\.(csv|parquet|json|txt)$|/SUCCESS$' \
    > "$OUT/04_lr_all_files.txt"


# ── 6. Unique filename patterns (strip run-id + timestamp)
echo "[6/8] Unique filename patterns →  05_lr_file_types.txt"
awk -F'/' '{print $NF}' "$OUT/04_lr_all_files.txt" \
    | sed -E 's|_2026-[0-9]+-[0-9]+_[0-9]+-[0-9]+-[0-9]+\.|_YYYY-MM-DD_HH-MM-SS.|' \
    | sed -E 's|_[0-9]{8}\.|_YYYYMMDD.|' \
    | sort -u > "$OUT/05_lr_file_types.txt"


# ── 7. Preview the 3 most-recent CSVs (small download, first 5 lines)
echo "[7/8] Preview 3 most-recent LR CSVs →  06_lr_previews/"
recent_csvs=$(grep -E '\.csv$' "$OUT/04_lr_all_files.txt" | tail -3)
while IFS= read -r uri; do
    [ -z "$uri" ] && continue
    fname=$(basename "$uri")
    echo "    ... previewing $fname"
    gcloud storage cp "$uri" "$OUT/06_lr_previews/$fname" 2>/dev/null
    if [ -f "$OUT/06_lr_previews/$fname" ]; then
        {
            echo "── $uri"
            echo "── size: $(ls -lh "$OUT/06_lr_previews/$fname" | awk '{print $5}')"
            echo "── row count: $(wc -l < "$OUT/06_lr_previews/$fname")"
            echo "── first 5 lines:"
            head -5 "$OUT/06_lr_previews/$fname"
        } > "$OUT/06_lr_previews/${fname}.preview.txt"
    fi
done <<< "$recent_csvs"


# ── 8. Audience uploads bucket
echo "[8/8] picknpay_audience_uploads contents →  07_audience_uploads.txt"
gcloud storage ls --recursive "gs://picknpay_audience_uploads/**" 2>/dev/null \
    > "$OUT/07_audience_uploads.txt"


# ── Consolidated summary
echo
echo "Writing summary → 08_summary.txt"
{
    echo "═══════════════════════════════════════════════════════"
    echo "  LiveRamp inventory summary"
    echo "  Generated $(date '+%Y-%m-%d %H:%M:%S')"
    echo "═══════════════════════════════════════════════════════"
    echo
    echo "── PicknPay tables in $PROD.PicknPay ──"
    grep -E '^\| [A-Za-z_]+ ' "$OUT/00_tables.txt" | head -30 || echo "  (see 00_tables.txt)"
    echo
    echo "── Total tables: $(grep -cE '^\| [A-Za-z_]+ ' "$OUT/00_tables.txt")"
    echo "── Total columns across all tables: $(grep -cE '^\| [A-Za-z_]+ .* \| [A-Z0-9]+ ' "$OUT/01_schemas.txt")"
    echo
    echo "── LR output partitions: $(wc -l < "$OUT/03_lr_partitions.txt") date folders"
    echo "── LR output files: $(wc -l < "$OUT/04_lr_all_files.txt") total"
    echo "── LR unique filename patterns: $(wc -l < "$OUT/05_lr_file_types.txt")"
    echo
    echo "── Unique LR question output types (top 20):"
    head -20 "$OUT/05_lr_file_types.txt" | sed 's/^/  /'
    echo
    echo "── Audience-upload bucket contents:"
    wc -l < "$OUT/07_audience_uploads.txt" | awk '{print "  " $1 " files"}'
    head -20 "$OUT/07_audience_uploads.txt" | sed 's/^/  /'
} > "$OUT/08_summary.txt"


echo
echo "════════════════════════════════════════════════════════════"
echo "  DONE. Everything dumped to $OUT/"
echo
echo "  On-screen summary:"
cat "$OUT/08_summary.txt"
echo
echo "  For details:"
echo "    cat $OUT/00_tables.txt          # tables + row counts"
echo "    cat $OUT/01_schemas.txt         # every column of every table"
echo "    ls  $OUT/02_samples/            # 5 rows per top-5 table"
echo "    cat $OUT/05_lr_file_types.txt   # unique LR question outputs"
echo "    ls  $OUT/06_lr_previews/        # 3 most-recent CSVs downloaded"
echo "════════════════════════════════════════════════════════════"
