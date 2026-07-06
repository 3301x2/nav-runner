#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Diagnose the "sandbox.staging exists but load says Not found" issue.
#
# Most likely: the dataset was created in a DIFFERENT location than
# africa-south1, and BQ treats mismatched-location targets as "not found".
#
# Also possible: name/casing mismatch, or dataset lives in a different
# project than fmn-sandbox.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SANDBOX="fmn-sandbox"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Sandbox staging dataset diagnosis"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. All datasets in $SANDBOX (any location) ──"
bq --project_id="$SANDBOX" ls --max_results=50


echo
echo "── 2. All datasets in $SANDBOX, US location ──"
bq --project_id="$SANDBOX" ls --location=US --max_results=50 2>&1 | head -20


echo
echo "── 3. All datasets in $SANDBOX, EU location ──"
bq --project_id="$SANDBOX" ls --location=EU --max_results=50 2>&1 | head -20


echo
echo "── 4. All datasets in $SANDBOX, africa-south1 location ──"
bq --project_id="$SANDBOX" ls --location=africa-south1 --max_results=50 2>&1 | head -20


echo
echo "── 5. Show details of 'staging' dataset if it exists ──"
bq --project_id="$SANDBOX" show --format=prettyjson "${SANDBOX}:staging" 2>&1 | head -30


echo
echo "── 6. Also try common variants (Staging, STAGING, stg, sandbox_staging) ──"
for variant in Staging STAGING stg sandbox_staging stage; do
    result=$(bq --project_id="$SANDBOX" show --format=prettyjson "${SANDBOX}:${variant}" 2>&1)
    if echo "$result" | grep -q "location"; then
        loc=$(echo "$result" | grep -i '"location"' | head -1)
        echo "   ✓ Found: ${variant}   $loc"
    fi
done


echo
echo "── 7. What location am I trying to write to? ──"
echo "   The load uses --location=africa-south1"
echo "   If the dataset location above is different, the load can't find it."


echo
echo "════════════════════════════════════════════════════════════"
echo "  Read section 5 for the actual location. If it's not"
echo "  africa-south1, that's why the load fails."
echo "════════════════════════════════════════════════════════════"
