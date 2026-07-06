#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Show every GCP project the account can see that mentions "fmn".
# If there are TWO prod projects (e.g. fmn-production AND fmn-production-462814),
# Rory may have granted access on one while my scripts target the other.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

echo
echo "════════════════════════════════════════════════════════════"
echo "  Every FMN project this account can see"
echo "════════════════════════════════════════════════════════════"

ACCOUNT=$(gcloud auth list --filter=status:ACTIVE --format="value(account)" 2>/dev/null | head -1)
echo
echo "Active account: $ACCOUNT"

echo
echo "── All projects the account can list (unfiltered) ──"
gcloud projects list --format="table(projectId,name,projectNumber)" 2>&1


echo
echo "── Same list, filtered to anything matching FMN ──"
gcloud projects list \
    --filter="projectId:fmn OR name:FMN OR name:fmn OR name:'FMN'" \
    --format="table(projectId,name,projectNumber)" 2>&1


echo
echo "── Test access on candidate prod project IDs ──"
for candidate in "fmn-production" "fmn-production-462814" "fmn-prod" "FMN-Production"; do
    echo
    echo "   Testing project ID: $candidate"
    if bq --project_id="$candidate" ls 2>/tmp/probe.log; then
        echo "   ✓ Access works — can list datasets in $candidate"
    else
        head -3 /tmp/probe.log 2>/dev/null | sed 's/^/       /'
    fi
done

echo
echo "════════════════════════════════════════════════════════════"
echo "  Send the output back. Look for:"
echo "  1. Is there ONE prod project or TWO with similar names?"
echo "  2. Which project ID does ✓ Access works — that's the real prod."
echo "════════════════════════════════════════════════════════════"
