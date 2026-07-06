#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Diagnostic — check exactly what access you have on fmn-sandbox and
# fmn-production-462014 so you can tell Rory precisely what's missing.
#
# Checks:
#   1. Which account you're authenticated as
#   2. Project-level IAM roles on both projects
#   3. Whether staging dataset exists in each project
#   4. Whether you can read gs://testing-sandbox-123 (the CSV bucket)
#   5. Whether you can list buckets in each project
#   6. Verdict per required permission
#
# Usage:
#   bash scripts/check_my_access.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SANDBOX="fmn-sandbox"
PROD="fmn-production-462014"
CSV_BUCKET="testing-sandbox-123"
CSV_OBJECT="ASPIRE_PRIMELIFE_20260706_FB.csv"

# Colours (bash-native, works in most terminals)
GREEN=$'\033[0;32m'
RED=$'\033[0;31m'
YELLOW=$'\033[0;33m'
NC=$'\033[0m'

ok()   { echo "${GREEN}✓${NC} $1"; }
bad()  { echo "${RED}✗${NC} $1"; }
warn() { echo "${YELLOW}!${NC} $1"; }

echo
echo "════════════════════════════════════════════════════════════"
echo "  Access diagnostic"
echo "════════════════════════════════════════════════════════════"

# ── 1. Current identity ──────────────────────────────────────────────
echo
echo "── 1. Who am I authenticated as? ──"
ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
if [ -z "$ACCOUNT" ]; then
    bad "No active gcloud auth. Run: gcloud auth login"
    exit 1
fi
ok "Active account: $ACCOUNT"


# ── 2. IAM roles per project ─────────────────────────────────────────
check_project_roles() {
    local project="$1"
    echo
    echo "── 2. Roles on $project ──"

    local roles
    roles=$(gcloud projects get-iam-policy "$project" \
        --flatten="bindings[].members" \
        --filter="bindings.members:$ACCOUNT" \
        --format="value(bindings.role)" 2>/dev/null | sort -u)

    if [ -z "$roles" ]; then
        bad "No roles found on $project (or you can't read the IAM policy)"
        return
    fi

    echo "$roles" | while read -r role; do
        [ -z "$role" ] && continue
        echo "   • $role"
    done

    # Check for each required role
    echo
    echo "   Required for the audience load:"
    for req in "roles/bigquery.user" "roles/bigquery.dataEditor" "roles/storage.objectViewer"; do
        if echo "$roles" | grep -qx "$req"; then
            ok "  $req"
        else
            # A superset role like Owner or Editor also satisfies these
            if echo "$roles" | grep -qxE "roles/(owner|editor)"; then
                warn "  $req (satisfied by owner/editor role above)"
            else
                bad "  $req — MISSING"
            fi
        fi
    done
}

check_project_roles "$SANDBOX"
check_project_roles "$PROD"


# ── 3. Dataset existence ─────────────────────────────────────────────
check_dataset() {
    local project="$1"
    echo
    echo "── 3. Does $project have a 'staging' dataset? ──"
    if bq --project_id="$project" show --dataset "${project}:staging" >/dev/null 2>&1; then
        ok "staging dataset exists in $project"
    else
        bad "staging dataset MISSING in $project"
    fi
}
check_dataset "$SANDBOX"
check_dataset "$PROD"


# ── 4. GCS read on the CSV bucket ────────────────────────────────────
echo
echo "── 4. Can I read gs://$CSV_BUCKET/$CSV_OBJECT? ──"
if gcloud storage ls "gs://$CSV_BUCKET/$CSV_OBJECT" >/dev/null 2>&1; then
    ok "CSV is readable"
else
    bad "Cannot read gs://$CSV_BUCKET/$CSV_OBJECT — no objectViewer or wrong path"
fi


# ── 5. Can I list buckets in each project? ───────────────────────────
echo
echo "── 5. Can I list buckets in each project? ──"
for project in "$SANDBOX" "$PROD"; do
    count=$(gcloud storage buckets list --project="$project" --format="value(name)" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$count" -gt 0 ]; then
        ok "$project: can see $count bucket(s)"
    else
        warn "$project: no buckets visible (either none exist or missing permission)"
    fi
done


# ── 6. Verdict — tell Rory exactly what to grant ────────────────────
echo
echo "════════════════════════════════════════════════════════════"
echo "  What to tell Rory"
echo "════════════════════════════════════════════════════════════"
echo
echo "For any ${RED}✗ MISSING${NC} role above, send Rory:"
echo
echo "gcloud projects add-iam-policy-binding <PROJECT> \\"
echo "    --member=\"user:$ACCOUNT\" \\"
echo "    --role=\"<MISSING_ROLE>\" \\"
echo "    --condition=None"
echo
echo "For any ${RED}✗ MISSING${NC} staging dataset, ask him to run in BQ:"
echo
echo "CREATE SCHEMA IF NOT EXISTS \`<PROJECT>.staging\`"
echo "OPTIONS (location = \"africa-south1\");"
echo
echo "Or you can create the dataset yourself once you have roles/bigquery.user."
echo "════════════════════════════════════════════════════════════"
