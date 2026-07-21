#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Ingest ONLY the LiveRamp clean-room outputs from gs://liveramp_output/
# into sandbox for analysis. Also loads gs://picknpay_audience_uploads/*.
#
# We do NOT copy fmn-production-462014.PicknPay tables. They already exist
# in prod BigQuery and are queryable directly. No duplication.
#
# What lands in sandbox:
#   fmn-sandbox.pnp_liveramp.lr_out_<question>   (one per LR question type)
#   fmn-sandbox.pnp_liveramp.aud_<name>          (one per audience upload file)
#
# Read from GCS, write to sandbox. Nothing hits local disk beyond a few kB
# of BQ job metadata. No CSVs pulled locally.
#
# Usage:
#   bash scripts/ingest_liveramp_to_sandbox.sh [--dry-run]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
    DRY_RUN=1
fi

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
FQ="$SB:$DS"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Ingest LiveRamp GCS outputs -> $SB.$DS"
echo "  Source: gs://liveramp_output/ + gs://picknpay_audience_uploads/"
echo "  (PicknPay tables in prod are queried in place, not copied)"
if [ "$DRY_RUN" = "1" ]; then echo "  DRY-RUN mode: no writes, just prints planned actions"; fi
echo "════════════════════════════════════════════════════════════"


# ── 1. Ensure sandbox dataset exists ────────────────────────────────────
echo
echo "── 1. Ensure $FQ dataset exists ──"
if bq --project_id="$SB" --location=africa-south1 show --dataset "$FQ" >/dev/null 2>&1; then
    echo "  ✓ $FQ already exists"
else
    if [ "$DRY_RUN" = "1" ]; then
        echo "  would run: bq mk --location=africa-south1 --dataset $FQ"
    else
        bq --project_id="$SB" mk --location=africa-south1 --dataset \
            --description "LiveRamp clean-room outputs + audience-upload files, mirrored from GCS for sandbox analysis" \
            "$FQ" \
            && echo "  ✓ created $FQ" \
            || { echo "  ❌ failed to create $FQ"; exit 1; }
    fi
fi


# ── 2. Load LR clean-room outputs from gs://liveramp_output/ ────────────
echo
echo "── 2. Load LR clean-room outputs from gs://liveramp_output/ ──"
echo "  (each unique question type becomes one table lr_out_<question>)"

# Filename patterns seen:
#   <QuestionName>_YYYY-MM-DD_HH-MM-SS.(csv|parquet)
#   Extract_DDMMYYYY_YYYY-MM-DD_HH-MM-SS.parquet   (double timestamp)
#
# Strategy: list every source file, derive its target table name from the
# filename, then pick ONE canonical file per table (prefer PARQUET over CSV
# because PARQUET has a real schema; on ties, take the newest). This avoids
# the phantom "Test"/"Export" question names from the naive split and stops
# CSV/PARQUET pairs from silently overwriting each other.

all_files_raw=$(gcloud storage ls --recursive "gs://liveramp_output/**" 2>/dev/null \
    | grep -Ei '\.(csv|parquet)$' \
    | grep -viE '/(SUCCESS|metadata\.json)$' )

# Build "tbl<TAB>uri" pairs, then group by tbl to pick one canonical source.
pairs=$(echo "$all_files_raw" | while IFS= read -r uri; do
    [ -z "$uri" ] && continue
    fname=$(basename "$uri")
    # Strip extension, then the trailing "_YYYY-MM-DD_HH-MM-SS" block.
    # This preserves "Test_Export" as one name (question stem), and reduces
    # "Extract_18022026_2026-02-18_09-54-59" to "Extract_18022026".
    stem=$(printf '%s' "$fname" \
        | sed -E 's/\.csv$//; s/\.parquet$//' \
        | sed -E 's/_2026-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$//')
    # Lower-case + sanitise for BQ table name.
    tbl="lr_out_$(printf '%s' "$stem" | tr '[:upper:]' '[:lower:]' \
        | sed -E 's|[^a-z0-9_]+|_|g; s|^_+||; s|_+$||')"
    [ "$tbl" = "lr_out_" ] && continue
    printf '%s\t%s\n' "$tbl" "$uri"
done)

# Distinct table names, in stable order.
uniq_tbls=$(echo "$pairs" | awk -F'\t' '{print $1}' | sort -u)

for tbl in $uniq_tbls; do
    [ -z "$tbl" ] && continue
    # All sources for this table, sorted with PARQUET last (so tail -1 wins).
    # First key: prefer parquet (put csv first, parquet second, tail picks parquet).
    # Second key: newest wins within a format group.
    src=$(echo "$pairs" | awk -F'\t' -v t="$tbl" '$1 == t {print $2}' \
        | awk '{
            fmt = ($0 ~ /\.parquet$/) ? "1_parquet" : "0_csv"
            print fmt "\t" $0
          }' \
        | sort \
        | tail -1 \
        | cut -f2)
    [ -z "$src" ] && continue

    ext="${src##*.}"
    fmt="CSV"; [ "$ext" = "parquet" ] && fmt="PARQUET"

    if [ "$DRY_RUN" = "1" ]; then
        echo "  would load $src -> $FQ.$tbl (as $fmt)"
        continue
    fi

    echo "  ... loading $tbl ($fmt)"
    if [ "$fmt" = "CSV" ]; then
        bq load --location=africa-south1 --replace --source_format=CSV \
            --autodetect --skip_leading_rows=1 \
            --preserve_ascii_control_characters \
            --max_bad_records=1000 \
            "$FQ.$tbl" "$src" >/dev/null 2>&1 \
            && echo "    ✓ $tbl" \
            || echo "    ❌ $tbl (bq load failed, check schema/PII policy)"
    else
        bq load --location=africa-south1 --replace --source_format=PARQUET \
            "$FQ.$tbl" "$src" >/dev/null 2>&1 \
            && echo "    ✓ $tbl" \
            || echo "    ❌ $tbl (bq load failed)"
    fi
done


# ── 3. Load audience uploads bucket ─────────────────────────────────────
echo
echo "── 3. Load audience uploads from gs://picknpay_audience_uploads/ ──"
aud_files=$(gcloud storage ls --recursive "gs://picknpay_audience_uploads/**" 2>/dev/null \
    | grep -Ei '\.(csv|parquet)$')

for src in $aud_files; do
    fname=$(basename "$src" | sed -E 's/\.csv$//; s/\.parquet$//')
    tbl="aud_$(echo "$fname" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9_]+/_/g' | sed -E 's/^_+//; s/_+$//')"
    ext="${src##*.}"
    fmt="CSV"; [ "$ext" = "parquet" ] && fmt="PARQUET"

    if [ "$DRY_RUN" = "1" ]; then
        echo "  would load $src -> $FQ.$tbl (as $fmt)"
        continue
    fi

    echo "  ... loading $(basename "$src") ($fmt) -> $tbl"
    if [ "$fmt" = "CSV" ]; then
        bq load --location=africa-south1 --replace --source_format=CSV \
            --autodetect --skip_leading_rows=1 \
            --preserve_ascii_control_characters \
            --max_bad_records=1000 \
            "$FQ.$tbl" "$src" >/dev/null 2>&1 \
            && echo "    ✓ $tbl" \
            || echo "    ❌ $tbl (bq load failed)"
    else
        bq load --location=africa-south1 --replace --source_format=PARQUET \
            "$FQ.$tbl" "$src" >/dev/null 2>&1 \
            && echo "    ✓ $tbl" \
            || echo "    ❌ $tbl (bq load failed)"
    fi
done


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo "  Next: bash scripts/discover_pnp_sandbox.sh"
echo "════════════════════════════════════════════════════════════"
