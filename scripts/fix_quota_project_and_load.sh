#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# The Google Cloud console can see fmn-production-462014 clearly (with
# datasets: Adidas, ETL_DEV, Metropolitan, PicknPay, demographics_*, etc.)
# but the gcloud CLI says "Project not found or deleted."
#
# Most likely cause: the ADC quota project is set to something wrong (or
# not set at all), so all API calls get billed to a project we don't have
# serviceusage.services.use on — which comes back as "not found."
#
# This script:
#   1. Shows which account is active
#   2. Explicitly sets the ADC quota project to fmn-production-462014
#   3. Runs a bare `bq ls` to confirm the CLI can now see prod datasets
#   4. Runs the prod load
#
# Usage:
#   bash scripts/fix_quota_project_and_load.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROD="fmn-production-462014"

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
NC=$'\033[0m'

ok()  { echo "${GREEN}✓${NC} $1"; }
bad() { echo "${RED}✗${NC} $1"; }

echo
echo "════════════════════════════════════════════════════════════"
echo "  Set ADC quota project + run prod load"
echo "════════════════════════════════════════════════════════════"


# ── 1. Show active account (should be the one that owns prod access) ─
echo
echo "── 1. Active account ──"
gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | sed 's/^/   /'


# ── 2. Set the ADC quota project explicitly ─────────────────────────
echo
echo "── 2. Set ADC quota project to $PROD ──"
if gcloud auth application-default set-quota-project "$PROD" 2>&1 | sed 's/^/   /'; then
    ok "Quota project set"
else
    bad "Could not set quota project — may need serviceusage.services.use permission"
fi


# ── 3. Prove the CLI can now see prod ────────────────────────────────
echo
echo "── 3. List datasets in $PROD (proves CLI + auth are aligned) ──"
if bq --project_id="$PROD" ls 2>&1 | sed 's/^/   /'; then
    ok "Datasets listed"
else
    bad "Still can't list — see error above"
fi


# ── 4. Run the load ──────────────────────────────────────────────────
echo
echo "════════════════════════════════════════════════════════════"
echo "  Running the Aspire audience load"
echo "════════════════════════════════════════════════════════════"
echo
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
bash "$SCRIPT_DIR/load_aspire_audience.sh" production
