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
#   Extract_DDMMYYYY_YYYY-MM-DD_HH-MM-SS.parquet
uniq_qs=$(gcloud storage ls --recursive "gs://liveramp_output/**" 2>/dev/null \
    | grep -Ei '\.(csv|parquet)$' \
    | awk -F'/' '{print $NF}' \
    | sed -E 's|_2026-[0-9]+-[0-9]+_[0-9]+-[0-9]+-[0-9]+\.(csv|parquet)$||' \
    | sed -E 's|_[0-9]{8}$||' \
    | sort -u)

for q in $uniq_qs; do
    tbl="lr_out_$(echo "$q" | tr '[:upper:]' '[:lower:]' | sed -E 's|[^a-z0-9_]+|_|g' | sed -E 's|^_+||;s|_+$||')"
    # newest file matching this question across all date folders
    src=$(gcloud storage ls --recursive "gs://liveramp_output/**/${q}_*" 2>/dev/null \
        | grep -Ei '\.(csv|parquet)$' \
        | sort \
        | tail -1)
    [ -z "$src" ] && { echo "  ⏭  no source for $q"; continue; }

    ext="${src##*.}"
    fmt="CSV"
    [ "$ext" = "parquet" ] && fmt="PARQUET"

    if [ "$DRY_RUN" = "1" ]; then
        echo "  would load $src -> $FQ.$tbl (as $fmt)"
        continue
    fi

    echo "  ... loading $q ($fmt) -> $tbl"
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
    fname=$(basename "$src" | sed -E 's|\.(csv|parquet)$||')
    tbl="aud_$(echo "$fname" | tr '[:upper:]' '[:lower:]' | sed -E 's|[^a-z0-9_]+|_|g' | sed -E 's|^_+||;s|_+$||')"
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
