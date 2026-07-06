#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Does everything Prosper can do with current access, then lists exactly
# what's still blocking so we can send Rory a precise ask.
#
# Actions attempted:
#   1. Create fmn-sandbox.staging dataset (if missing)
#   2. Try to create fmn-production-462814.staging dataset (probably fails —
#      that's fine, we'll tell Rory)
#   3. List what's actually in gs://testing-sandbox-123 (so we can see
#      if the file name is different from what we expected)
#   4. Try to load the CSV into sandbox (will fail if the bucket-level
#      block is real — the error message tells us which)
#
# Nothing here is destructive: uses `mk` (safe to re-run, does nothing
# if dataset exists), `--replace` on the load ONLY overwrites the target
# BQ table, not the source CSV.
#
# Usage:
#   bash scripts/do_what_i_can.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SANDBOX="fmn-sandbox"
PROD="fmn-production-462814"
CSV_BUCKET="testing-sandbox-123"
CSV_OBJECT="ASPIRE_PRIMELIFE_20260706_FB.csv"
TABLE="${SANDBOX}.staging.aspire_primelife_meta_audience"
LOCATION="africa-south1"

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

ok()   { echo "${GREEN}✓${NC} $1"; }
bad()  { echo "${RED}✗${NC} $1"; }
warn() { echo "${YELLOW}!${NC} $1"; }

# Track what worked so we can summarise for Rory
declare -a NEED_FROM_RORY

echo
echo "════════════════════════════════════════════════════════════"
echo "  Doing what I can with current access"
echo "════════════════════════════════════════════════════════════"


# ── 1. Auth check ─────────────────────────────────────────────────────
echo
echo "── 1. Auth check ──"
ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
if [ -z "$ACCOUNT" ]; then
    bad "No active gcloud auth. Run: gcloud auth login"
    exit 1
fi
ok "Authenticated as $ACCOUNT"


# ── 2. Create sandbox staging dataset ────────────────────────────────
echo
echo "── 2. Create fmn-sandbox.staging dataset ──"
if bq --project_id="$SANDBOX" show --dataset "${SANDBOX}:staging" >/dev/null 2>&1; then
    ok "$SANDBOX.staging already exists"
else
    if bq --project_id="$SANDBOX" mk \
        --location="$LOCATION" \
        --dataset \
        --description="Staging tables — audience loads etc" \
        "${SANDBOX}:staging" 2>&1 | tee /tmp/mk_sandbox.log; then
        ok "Created $SANDBOX.staging"
    else
        bad "Failed to create $SANDBOX.staging"
        cat /tmp/mk_sandbox.log
        NEED_FROM_RORY+=("Create dataset in sandbox — I don't have bigquery.datasets.create")
    fi
fi


# ── 3. Try to create prod staging dataset ────────────────────────────
echo
echo "── 3. Try to create fmn-production-462814.staging dataset ──"
if bq --project_id="$PROD" show --dataset "${PROD}:staging" >/dev/null 2>&1; then
    ok "$PROD.staging already exists"
else
    if bq --project_id="$PROD" mk \
        --location="$LOCATION" \
        --dataset \
        --description="Staging tables — audience loads etc" \
        "${PROD}:staging" 2>/tmp/mk_prod.log; then
        ok "Created $PROD.staging"
    else
        warn "Couldn't create $PROD.staging (expected — missing bigquery.user on prod)"
        cat /tmp/mk_prod.log | head -3
        NEED_FROM_RORY+=("Grant roles/bigquery.user + roles/bigquery.dataEditor on $PROD")
    fi
fi


# ── 4. Inspect the bucket ────────────────────────────────────────────
echo
echo "── 4. What's actually in gs://$CSV_BUCKET/ ──"
if gcloud storage ls "gs://$CSV_BUCKET/" 2>/tmp/ls_bucket.log; then
    ok "Bucket listing succeeded"
else
    bad "Cannot list bucket contents"
    cat /tmp/ls_bucket.log | head -3
    NEED_FROM_RORY+=("Bucket-level access to gs://$CSV_BUCKET is missing — my project-level storage.objectAdmin isn't kicking in")
fi


# ── 5. Confirm CSV specifically is readable ──────────────────────────
echo
echo "── 5. Can I read gs://$CSV_BUCKET/$CSV_OBJECT? ──"
if gcloud storage ls "gs://$CSV_BUCKET/$CSV_OBJECT" >/dev/null 2>&1; then
    ok "CSV is readable"
    CSV_OK=true
else
    bad "Cannot read the CSV"
    CSV_OK=false
    NEED_FROM_RORY+=("Grant read on gs://$CSV_BUCKET/$CSV_OBJECT specifically, or fix bucket-level ACL")
fi


# ── 6. Attempt the sandbox load if we can ────────────────────────────
echo
echo "── 6. Attempt to load CSV into $TABLE ──"
if [ "${CSV_OK:-false}" = "true" ]; then
    if bq --project_id="$SANDBOX" load \
        --location="$LOCATION" \
        --source_format=CSV \
        --replace \
        --skip_leading_rows=1 \
        --allow_quoted_newlines \
        --max_bad_records=0 \
        --schema="email:STRING,email2:STRING,email3:STRING,phone:STRING,phone2:STRING,phone3:STRING,madid:STRING,fn:STRING,ln:STRING,zip:STRING,ct:STRING,st:STRING,country:STRING,dob:STRING,doby:STRING,gen:STRING,age:STRING,uid:STRING" \
        "$TABLE" \
        "gs://$CSV_BUCKET/$CSV_OBJECT" 2>/tmp/load.log; then
        ok "Loaded CSV into $TABLE"
        LOAD_OK=true
    else
        bad "Load failed — see error below"
        cat /tmp/load.log | head -15
        LOAD_OK=false
        NEED_FROM_RORY+=("CSV load failed — see error above; may need bucket read fix")
    fi
else
    warn "Skipping load — can't read CSV"
    LOAD_OK=false
fi


# ── 7. If load worked, run row count as smoke test ───────────────────
if [ "${LOAD_OK:-false}" = "true" ]; then
    echo
    echo "── 7. Row count smoke test ──"
    bq query --quiet --use_legacy_sql=false --project_id="$SANDBOX" \
        --format=pretty "SELECT COUNT(*) AS rows_loaded FROM \`$TABLE\`" 2>/dev/null
fi


# ── 8. Summary ───────────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════"
echo "  SUMMARY"
echo "════════════════════════════════════════════════════════════"

if [ ${#NEED_FROM_RORY[@]} -eq 0 ]; then
    ok "Nothing left to do — everything succeeded"
else
    echo
    echo "Still need from Rory:"
    for item in "${NEED_FROM_RORY[@]}"; do
        echo "   • $item"
    done
    echo
    echo "See MESSAGE_FOR_RORY.md for the copy-paste message to send him."
fi

echo
