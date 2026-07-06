#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Check whether Prosper can now do the sandbox → prod bq cp.
#
# Runs three specific tests:
#   1. Can I read the sandbox table? (should be yes)
#   2. Can I list datasets in fmn-production-462814?
#   3. Can I create a dataset in fmn-production-462814? (dry-run using --dry_run
#      style — attempt to create a temp one, then delete)
#   4. What roles do I actually have on fmn-production-462814?
#
# Usage:
#   bash scripts/check_prod_access.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SANDBOX="fmn-sandbox"
PROD="fmn-production-462814"
SANDBOX_TABLE="fmn-sandbox:staging.aspire_primelife_meta_audience"

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

ok()   { echo "${GREEN}✓${NC} $1"; }
bad()  { echo "${RED}✗${NC} $1"; }
warn() { echo "${YELLOW}!${NC} $1"; }

echo
echo "════════════════════════════════════════════════════════════"
echo "  Can I do the sandbox → prod copy yet?"
echo "════════════════════════════════════════════════════════════"

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
echo
echo "Authenticated as: $ACCOUNT"


echo
echo "── 1. Can I read the sandbox source table? ──"
if bq --project_id="$SANDBOX" show "$SANDBOX_TABLE" >/dev/null 2>&1; then
    ok "Sandbox table readable"
else
    bad "Cannot read sandbox table — problem on sandbox side"
fi


echo
echo "── 2. Can I list datasets in $PROD? ──"
if bq --project_id="$PROD" ls >/dev/null 2>&1; then
    ok "Can list datasets in $PROD"
    echo "   Datasets found:"
    bq --project_id="$PROD" ls 2>/dev/null | sed 's/^/     /'
else
    bad "Cannot list datasets in $PROD — need bigquery.jobUser or higher"
fi


echo
echo "── 3. Does fmn-production-462814.staging exist? ──"
if bq --project_id="$PROD" show --dataset "${PROD}:staging" >/dev/null 2>&1; then
    ok "${PROD}:staging exists"
    DATASET_OK=true
else
    warn "${PROD}:staging does NOT exist yet"
    DATASET_OK=false
fi


echo
echo "── 4. Can I create a dataset in $PROD? (test the permission) ──"
TEST_DATASET="${PROD}:_prosper_probe_$$"
if bq --project_id="$PROD" mk --location=africa-south1 --dataset "$TEST_DATASET" >/dev/null 2>&1; then
    ok "Can create datasets in $PROD"
    # Clean up
    bq --project_id="$PROD" rm -f -d "$TEST_DATASET" >/dev/null 2>&1
    CAN_CREATE=true
else
    bad "Cannot create datasets in $PROD — need roles/bigquery.user"
    CAN_CREATE=false
fi


echo
echo "── 5. My roles on $PROD ──"
gcloud projects get-iam-policy "$PROD" \
    --flatten="bindings[].members" \
    --filter="bindings.members:$ACCOUNT" \
    --format="value(bindings.role)" 2>/dev/null | sort -u | sed 's/^/   /' || \
    bad "Couldn't read IAM policy (may need extra permission)"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Verdict"
echo "════════════════════════════════════════════════════════════"
if [ "${DATASET_OK:-false}" = "true" ]; then
    ok "Ready — dataset exists, can proceed with:"
    echo "     bash scripts/load_aspire_audience.sh production"
elif [ "${CAN_CREATE:-false}" = "true" ]; then
    ok "Almost — I can create the dataset myself, then run:"
    echo "     bq --project_id=$PROD mk --location=africa-south1 --dataset ${PROD}:staging"
    echo "     bash scripts/load_aspire_audience.sh production"
else
    bad "Still blocked — need Rory to grant bigquery.user + bigquery.dataEditor on $PROD"
    echo "     See MESSAGE_FOR_RORY_PROD_ACCESS.txt"
fi
echo "════════════════════════════════════════════════════════════"
