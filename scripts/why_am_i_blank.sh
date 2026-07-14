#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Why are queries returning blank? Runs the exact same operations as
# count_vox_identifiers.sh but WITHOUT suppressing stderr — so we see
# the real error instead of silent nothing.
# ─────────────────────────────────────────────────────────────────────────

# NB: no `set -uo pipefail` — we want everything to run even on error

PROJECT="fmn-production-462014"
DATASET="staging"
TABLE_NAME="vox_consent_inclusiona_meta_audience"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Diagnostic — why bq queries return blank"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. Who am I authenticated as? ──"
gcloud auth list
echo
gcloud config list


echo
echo "── 2. Is my access token still valid? ──"
if TOKEN=$(gcloud auth print-access-token 2>&1); then
    echo "   Token acquired (first 20 chars): ${TOKEN:0:20}..."
else
    echo "   ✗ FAILED to get token — this is your problem"
    echo "   $TOKEN"
    echo
    echo "   Fix: gcloud auth login"
    exit 1
fi


echo
echo "── 3. Are Application Default Credentials still valid? ──"
if ADC_TOKEN=$(gcloud auth application-default print-access-token 2>&1); then
    echo "   ADC token acquired (first 20 chars): ${ADC_TOKEN:0:20}..."
else
    echo "   ✗ FAILED to get ADC token"
    echo "   $ADC_TOKEN"
    echo
    echo "   Fix: gcloud auth application-default login"
fi


echo
echo "── 4. Can I list datasets in the target project? ──"
echo "   (running WITHOUT 2>/dev/null so we see the real error)"
bq --project_id="$PROJECT" ls
echo "   Exit code: $?"


echo
echo "── 5. Can I show the specific table? ──"
bq --project_id="$PROJECT" show "$PROJECT:$DATASET.$TABLE_NAME"
echo "   Exit code: $?"


echo
echo "── 6. Run the actual schema query, no stderr suppression ──"
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=pretty --max_rows=25 "
    SELECT column_name, data_type, ordinal_position
    FROM \`${PROJECT}.${DATASET}.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = '$TABLE_NAME'
    ORDER BY ordinal_position
"
echo "   Exit code: $?"


echo
echo "── 7. Run the simplest possible query (SELECT 1) ──"
bq query --project_id="$PROJECT" --use_legacy_sql=false --format=pretty "SELECT 1 AS test"
echo "   Exit code: $?"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Read the exit codes — 0 means the operation worked."
echo "  Anything non-zero + the error text above tells us what's up."
echo "════════════════════════════════════════════════════════════"
