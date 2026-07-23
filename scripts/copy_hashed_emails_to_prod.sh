#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Copy fmn-sandbox.temp_tables.dummy_hashed_emails to prod, dropping the
# plaintext original_email column so only the hashed_email remains.
#
# Uses a server-side CTAS (CREATE OR REPLACE TABLE AS SELECT). No local
# data hop, no PII leaves BigQuery. Runs the SELECT in prod so the job is
# billed correctly and the destination location resolves.
#
# Read from sandbox, write to prod. This is one of the very few scripts
# that writes to prod (the sandbox-default rule allows this for final
# promotion of already-verified sandbox tables).
#
# Usage:
#   bash scripts/copy_hashed_emails_to_prod.sh --dry-run   # preview
#   bash scripts/copy_hashed_emails_to_prod.sh             # do it
#
# Change SRC_TABLE / DST_TABLE / DST_DATASET / DST_COL below if any of
# those need to differ.
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
PROD="fmn-production-462014"

SRC_TABLE="$SB.temp_tables.dummy_hashed_emails"      # source in sandbox
DST_DATASET="temp_tables"                             # dataset in prod (mirrors sandbox)
DST_TABLE="$PROD.$DST_DATASET.dummy_hashed_emails"   # destination in prod
KEEP_COL="hashed_email"                               # column to keep
DROP_COL="original_email"                             # column to drop

echo
echo "════════════════════════════════════════════════════════════"
echo "  Copy sanitised hashed_email table to prod"
echo "  Source:      $SRC_TABLE"
echo "  Destination: $DST_TABLE"
echo "  Keep column: $KEEP_COL"
echo "  Drop column: $DROP_COL (plaintext PII, will NOT land in prod)"
if [ "$DRY_RUN" = "1" ]; then echo "  DRY-RUN mode: no writes, just prints the planned SQL + row count"; fi
echo "════════════════════════════════════════════════════════════"


# ── 1. Confirm source exists and count rows ─────────────────────────────
echo
echo "── 1. Source table sanity ──"
bq query --quiet --use_legacy_sql=false --project_id="$SB" \
    --location=africa-south1 --format=pretty --max_rows=5 "
    SELECT COUNT(*) AS n_rows,
           COUNTIF($KEEP_COL IS NULL) AS null_hashed,
           COUNTIF($DROP_COL IS NULL) AS null_plaintext
    FROM \`$SRC_TABLE\`
"


# ── 2. Ensure destination dataset exists in prod (create if missing) ────
echo
echo "── 2. Destination dataset check ──"
if bq --project_id="$PROD" --location=africa-south1 show --dataset "$PROD:$DST_DATASET" >/dev/null 2>&1; then
    echo "  ✓ $PROD:$DST_DATASET already exists"
else
    if [ "$DRY_RUN" = "1" ]; then
        echo "  would run: bq mk --location=africa-south1 --dataset $PROD:$DST_DATASET"
    else
        echo "  ⏳ $PROD:$DST_DATASET does not exist yet. Creating..."
        bq --project_id="$PROD" mk --location=africa-south1 --dataset \
            --description "Scratch/dummy tables. Not client data. Mirrors fmn-sandbox.temp_tables naming." \
            "$PROD:$DST_DATASET" \
            && echo "  ✓ created $PROD:$DST_DATASET" \
            || { echo "  ❌ failed to create $PROD:$DST_DATASET"; exit 1; }
    fi
fi


# ── 3. Warn if destination table already exists ─────────────────────────
echo
echo "── 3. Destination table pre-check ──"
if bq --project_id="$PROD" --location=africa-south1 show "$DST_TABLE" >/dev/null 2>&1; then
    existing_rows=$(bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
        --location=africa-south1 --format=csv --max_rows=1 \
        "SELECT COUNT(*) FROM \`$DST_TABLE\`" 2>/dev/null | tail -1)
    echo "  ⚠  Destination already exists with ${existing_rows:-?} rows."
    echo "     The CREATE OR REPLACE below will OVERWRITE it."
else
    echo "  ✓ Destination does not exist yet, will be created fresh"
fi


# ── 4. Show the SQL that will run ───────────────────────────────────────
CTAS_SQL="CREATE OR REPLACE TABLE \`$DST_TABLE\`
OPTIONS (
    description = 'Sanitised hashed_email table promoted from $SRC_TABLE. Plaintext $DROP_COL column stripped at promotion.'
)
AS
SELECT $KEEP_COL FROM \`$SRC_TABLE\`"

echo
echo "── 4. Planned SQL ──"
echo "$CTAS_SQL"


# ── 5. Execute (or skip if dry-run) ─────────────────────────────────────
if [ "$DRY_RUN" = "1" ]; then
    echo
    echo "── DRY-RUN: no execution. Re-run without --dry-run to promote."
    exit 0
fi

echo
echo "── 5. Running CTAS ──"
# We run the query IN THE PROD PROJECT so the destination table location
# resolves correctly. Prod has read access to sandbox tables (via IAM).
bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
    --location=africa-south1 "$CTAS_SQL" \
    && echo "  ✓ CTAS complete" \
    || { echo "  ❌ CTAS failed"; exit 1; }


# ── 6. Verify destination ───────────────────────────────────────────────
echo
echo "── 6. Verification ──"
bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
    --location=africa-south1 --format=pretty --max_rows=5 "
    SELECT COUNT(*) AS n_rows,
           COUNT(DISTINCT $KEEP_COL) AS n_distinct_hashed,
           COUNTIF($KEEP_COL IS NULL) AS n_null
    FROM \`$DST_TABLE\`
"

echo
echo "── 7. Confirm destination schema (should be ONE column: $KEEP_COL) ──"
bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
    --location=africa-south1 --format=pretty --max_rows=5 "
    SELECT column_name, data_type, ordinal_position
    FROM \`$PROD.$DST_DATASET.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = 'dummy_hashed_emails'
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done."
echo "  $DST_TABLE now has only $KEEP_COL. Plaintext dropped."
echo "════════════════════════════════════════════════════════════"
