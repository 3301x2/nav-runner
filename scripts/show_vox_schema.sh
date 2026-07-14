#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Show ONLY the Vox table schema — nothing else. So we can see the exact
# column names, then rewrite the count query to use them.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROJECT="fmn-production-462014"
DATASET="staging"
TABLE_NAME="vox_consent_inclusiona_meta_audience"

# Auto-refresh both user and ADC creds if either is dead
if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired — re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired — re-logging in..."
    gcloud auth application-default login
fi

echo
echo "════════════════════════════════════════════════════════════"
echo "  Column names in $PROJECT.$DATASET.$TABLE_NAME"
echo "════════════════════════════════════════════════════════════"

bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
    --format=pretty --max_rows=30 "
    SELECT column_name, data_type, ordinal_position
    FROM \`${PROJECT}.${DATASET}.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = '$TABLE_NAME'
    ORDER BY ordinal_position
" 2>/dev/null
