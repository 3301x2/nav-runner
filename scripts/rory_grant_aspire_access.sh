#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# For Rory to run — grants Prosper the minimum access needed to load the
# Aspire audience CSV into fmn-sandbox and copy it to fmn-production.
#
# Also creates the `staging` dataset in each project (needed for the load).
#
# Safe: only ADDS bindings, never removes. Idempotent — re-running is fine.
#
# Usage (Rory):
#   bash scripts/rory_grant_aspire_access.sh <prosper's email>
# e.g.
#   bash scripts/rory_grant_aspire_access.sh prosper.sikhwari@firstrand.co.za
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROSPER_EMAIL="${1:-}"
if [ -z "$PROSPER_EMAIL" ]; then
    echo "Usage: bash $0 <prosper's email>"
    echo "e.g.:  bash $0 prosper.sikhwari@firstrand.co.za"
    exit 1
fi

SANDBOX_PROJECT="fmn-sandbox"
PROD_PROJECT="fmn-production"
BUCKET="testing-sandbox-123"
CSV_OBJECT="ASPIRE_PRIMELIFE_20260706_FB.csv"
LOCATION="africa-south1"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Aspire audience — access grant for $PROSPER_EMAIL"
echo "════════════════════════════════════════════════════════════"

echo
echo "── 1. Grant BigQuery access on $SANDBOX_PROJECT ──"
# bigquery.user  = create/run jobs + create datasets
# bigquery.dataEditor = read/write data within datasets
for role in "roles/bigquery.user" "roles/bigquery.dataEditor"; do
    echo "   → $role"
    gcloud projects add-iam-policy-binding "$SANDBOX_PROJECT" \
        --member="user:$PROSPER_EMAIL" \
        --role="$role" \
        --condition=None \
        --quiet 2>&1 | tail -1
done

echo
echo "── 2. Grant BigQuery access on $PROD_PROJECT ──"
for role in "roles/bigquery.user" "roles/bigquery.dataEditor"; do
    echo "   → $role"
    gcloud projects add-iam-policy-binding "$PROD_PROJECT" \
        --member="user:$PROSPER_EMAIL" \
        --role="$role" \
        --condition=None \
        --quiet 2>&1 | tail -1
done

echo
echo "── 3. Grant GCS read on gs://$BUCKET (for the CSV load) ──"
gcloud storage buckets add-iam-policy-binding "gs://$BUCKET" \
    --member="user:$PROSPER_EMAIL" \
    --role="roles/storage.objectViewer" \
    --quiet 2>&1 | tail -1

echo
echo "── 4. Create staging dataset in $SANDBOX_PROJECT (if missing) ──"
bq --project_id="$SANDBOX_PROJECT" mk \
    --location="$LOCATION" \
    --dataset \
    --description="Staging tables — audience loads etc" \
    "${SANDBOX_PROJECT}:staging" 2>&1 | grep -v "already exists" || true

echo
echo "── 5. Create staging dataset in $PROD_PROJECT (if missing) ──"
bq --project_id="$PROD_PROJECT" mk \
    --location="$LOCATION" \
    --dataset \
    --description="Staging tables — audience loads etc" \
    "${PROD_PROJECT}:staging" 2>&1 | grep -v "already exists" || true

echo
echo "── 6. Verify — show Prosper's project-level roles ──"
echo
echo "$SANDBOX_PROJECT:"
gcloud projects get-iam-policy "$SANDBOX_PROJECT" \
    --flatten="bindings[].members" \
    --filter="bindings.members:$PROSPER_EMAIL" \
    --format="value(bindings.role)" 2>&1 | sort -u

echo
echo "$PROD_PROJECT:"
gcloud projects get-iam-policy "$PROD_PROJECT" \
    --flatten="bindings[].members" \
    --filter="bindings.members:$PROSPER_EMAIL" \
    --format="value(bindings.role)" 2>&1 | sort -u

echo
echo "── 7. Verify — show bucket-level roles on gs://$BUCKET ──"
gcloud storage buckets get-iam-policy "gs://$BUCKET" \
    --format="value(bindings.role)" 2>&1 | grep -i "prosper\|storage" || true

echo
echo "── 8. Confirm the CSV is readable ──"
gcloud storage ls "gs://$BUCKET/$CSV_OBJECT" 2>&1 || echo "   (couldn't list — check bucket + object name)"

echo
echo "── 9. Confirm both staging datasets exist ──"
bq --project_id="$SANDBOX_PROJECT" show --dataset "${SANDBOX_PROJECT}:staging" 2>&1 | head -3
bq --project_id="$PROD_PROJECT"    show --dataset "${PROD_PROJECT}:staging"    2>&1 | head -3

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. IAM propagation can take 1-3 minutes."
echo
echo "  Prosper: after Rory runs this, wait ~2 min, then re-auth:"
echo "    gcloud auth application-default login"
echo "  Then retry:"
echo "    bash scripts/load_aspire_audience.sh sandbox"
echo "════════════════════════════════════════════════════════════"
