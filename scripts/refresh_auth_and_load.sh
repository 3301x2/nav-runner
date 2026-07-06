#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Refresh gcloud auth so newly-granted IAM roles are picked up, then run
# the prod load. Use this when Rory just granted access but bq / gcloud
# are still hitting the old cached token.
#
# What it does:
#   1. Shows which account is currently active
#   2. Refreshes user credentials (gcloud auth login)
#   3. Refreshes Application Default Credentials (used by bq/BQ client libs)
#   4. Verifies IAM roles on both projects
#   5. Runs the prod load
#
# Usage:
#   bash scripts/refresh_auth_and_load.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SANDBOX="fmn-sandbox"
PROD="fmn-production"

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

ok()   { echo "${GREEN}✓${NC} $1"; }
bad()  { echo "${RED}✗${NC} $1"; }
warn() { echo "${YELLOW}!${NC} $1"; }

echo
echo "════════════════════════════════════════════════════════════"
echo "  Refresh auth + run prod load"
echo "════════════════════════════════════════════════════════════"


# ── 1. Show current active account ───────────────────────────────────
echo
echo "── 1. Currently active gcloud account ──"
gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | sed 's/^/   /'

echo
echo "   All configured accounts:"
gcloud auth list --format="value(account,status)" 2>/dev/null | sed 's/^/     /'


# ── 2. Refresh user credentials ──────────────────────────────────────
echo
echo "── 2. Refreshing user credentials (opens browser) ──"
echo "   If a browser opens, complete the sign-in. If not, follow the URL that appears."
if gcloud auth login --update-adc; then
    ok "User credentials refreshed"
else
    bad "gcloud auth login failed — check the error above"
    exit 1
fi


# ── 3. Refresh Application Default Credentials ───────────────────────
echo
echo "── 3. Refreshing Application Default Credentials ──"
echo "   These are the credentials the bq CLI + BigQuery client libs use."
if gcloud auth application-default login; then
    ok "ADC refreshed"
else
    bad "gcloud auth application-default login failed"
    exit 1
fi

# Also set the quota project so the ADC warning goes away
ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
gcloud auth application-default set-quota-project "$PROD" 2>/dev/null || true


# ── 4. Verify IAM roles on both projects ─────────────────────────────
echo
echo "── 4. IAM roles now visible on $SANDBOX ──"
gcloud projects get-iam-policy "$SANDBOX" \
    --flatten="bindings[].members" \
    --filter="bindings.members:$ACCOUNT" \
    --format="value(bindings.role)" 2>/dev/null | sort -u | sed 's/^/   /'

echo
echo "── 4. IAM roles now visible on $PROD ──"
gcloud projects get-iam-policy "$PROD" \
    --flatten="bindings[].members" \
    --filter="bindings.members:$ACCOUNT" \
    --format="value(bindings.role)" 2>/dev/null | sort -u | sed 's/^/   /'


# ── 5. Confirm the prod dataset situation ────────────────────────────
echo
echo "── 5. Can I see fmn-production.staging? ──"
if bq --project_id="$PROD" show --dataset "${PROD}:staging" >/dev/null 2>&1; then
    ok "${PROD}.staging exists"
else
    warn "${PROD}.staging does NOT exist yet — the load script will try to create it"
fi


# ── 6. Run the prod load ─────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════"
echo "  Running the prod load"
echo "════════════════════════════════════════════════════════════"
echo
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
bash "$SCRIPT_DIR/load_aspire_audience.sh" production
