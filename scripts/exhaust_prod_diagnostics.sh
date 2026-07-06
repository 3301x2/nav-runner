#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Before pinging Rory again, exhaust every plausible reason we can't
# do stuff on fmn-production. Prints a clean verdict at the end.
#
# Checks:
#   1. All gcloud accounts + which one is active
#   2. Full IAM binding dump for the account on fmn-production
#     (including conditional bindings and ancestor-level roles)
#   3. Real API access test — list datasets, list buckets, get a job
#   4. Quota project mismatch check
#   5. Retry the prod load with fresh error output
#
# Usage:
#   bash scripts/exhaust_prod_diagnostics.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROD="fmn-production"
SANDBOX="fmn-sandbox"

GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

ok()   { echo "${GREEN}✓${NC} $1"; }
bad()  { echo "${RED}✗${NC} $1"; }
warn() { echo "${YELLOW}!${NC} $1"; }

echo
echo "════════════════════════════════════════════════════════════"
echo "  Full prod-access diagnostics"
echo "════════════════════════════════════════════════════════════"


# ── 1. All accounts on gcloud ────────────────────────────────────────
echo
echo "── 1. All configured gcloud accounts ──"
gcloud auth list --format="value(account,status)" 2>/dev/null | sed 's/^/   /'
ACTIVE_ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
echo
echo "   Active account: $ACTIVE_ACCOUNT"


# ── 2. Application Default Credentials details ──────────────────────
echo
echo "── 2. ADC status (what bq CLI uses under the hood) ──"
ADC_ACCOUNT=$(gcloud auth application-default print-access-token 2>/dev/null | head -1 >/dev/null && echo "present" || echo "absent")
echo "   ADC token: $ADC_ACCOUNT"

QUOTA_PROJECT=$(cat ~/.config/gcloud/application_default_credentials.json 2>/dev/null | python3 -c "import sys, json; d=json.load(sys.stdin); print(d.get('quota_project_id','(none)'))" 2>/dev/null || echo "(couldn't read)")
echo "   ADC quota project: $QUOTA_PROJECT"


# ── 3. Project settings verification ─────────────────────────────────
echo
echo "── 3. Confirm project ID and number ──"
gcloud projects describe "$PROD" --format="value(projectId,projectNumber,name)" 2>&1 | sed 's/^/   /'


# ── 4. Full IAM policy dump for you on prod (raw JSON) ──────────────
echo
echo "── 4. All IAM bindings on $PROD mentioning your email ──"
echo "     (includes conditional bindings that regular listings hide)"
gcloud projects get-iam-policy "$PROD" --format=json 2>/dev/null | \
    python3 -c "
import sys, json
try:
    p = json.load(sys.stdin)
    hits = []
    for b in p.get('bindings', []):
        role = b.get('role','')
        members = b.get('members',[])
        cond = b.get('condition')
        for m in members:
            if '$ACTIVE_ACCOUNT' in m:
                hits.append((role, m, cond))
    if not hits:
        print('   (no bindings mention this account)')
    else:
        for role, m, cond in hits:
            print(f'   • Role:     {role}')
            print(f'     Member:   {m}')
            if cond:
                print(f'     Condition: {cond}')  # <-- if this shows up, that's the bug
            print()
except Exception as e:
    print(f'   (parse error: {e})')
"


# ── 5. Ancestor / folder level bindings ─────────────────────────────
echo
echo "── 5. Ancestor bindings (org/folder level) for the account ──"
gcloud policy-troubleshoot iam \
    "//cloudresourcemanager.googleapis.com/projects/$PROD" \
    --principal="$ACTIVE_ACCOUNT" \
    --permission="bigquery.jobs.create" 2>&1 | head -30 | sed 's/^/   /' || \
    warn "   policy-troubleshoot IAM not available or errored — skip"


# ── 6. Real API access tests ─────────────────────────────────────────
echo
echo "── 6. Real BQ access tests on $PROD ──"

echo
echo "   Test A: list datasets in $PROD"
if bq --project_id="$PROD" ls 2>/tmp/bq_ls.log; then
    ok "   Can list datasets"
else
    bad "   Cannot list datasets"
    head -3 /tmp/bq_ls.log 2>/dev/null | sed 's/^/       /'
fi

echo
echo "   Test B: run a trivial query (SELECT 1) on $PROD"
if bq query --quiet --use_legacy_sql=false --project_id="$PROD" \
    --format=pretty "SELECT 1 AS test" >/tmp/bq_query.log 2>&1; then
    ok "   Can run queries"
    cat /tmp/bq_query.log | sed 's/^/       /'
else
    bad "   Cannot run queries"
    head -6 /tmp/bq_query.log 2>/dev/null | sed 's/^/       /'
fi

echo
echo "   Test C: try to create a probe dataset in $PROD"
PROBE_DATASET="${PROD}:_prosper_probe_$$"
if bq --project_id="$PROD" mk --location=africa-south1 --dataset "$PROBE_DATASET" 2>/tmp/bq_mk.log; then
    ok "   Can create datasets"
    bq --project_id="$PROD" rm -f -d "$PROBE_DATASET" >/dev/null 2>&1
else
    bad "   Cannot create datasets"
    head -3 /tmp/bq_mk.log 2>/dev/null | sed 's/^/       /'
fi


# ── 7. Wait + retry the load (in case IAM is still propagating) ─────
echo
echo "── 7. Give IAM 30s to fully settle then retry the load ──"
sleep 30
SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
bash "$SCRIPT_DIR/load_aspire_audience.sh" production 2>&1 | tail -25


echo
echo "════════════════════════════════════════════════════════════"
echo "  Verdict — what to tell Rory (if we need to)"
echo "════════════════════════════════════════════════════════════"
echo "  If Test A + B + C all failed above → the roles genuinely aren't on prod."
echo "  If Test A works but C fails → dataEditor granted but bigquery.user missing."
echo "  If you see a 'Condition' in section 4 → the grant is conditional (bug)."
echo "  If section 5 showed org/folder role → the role IS there but not applied."
echo "════════════════════════════════════════════════════════════"
