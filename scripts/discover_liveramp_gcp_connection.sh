#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Discover any LiveRamp-to-GCP connection paths visible from our GCP creds.
#
# LiveRamp Clean Room typically connects to a bank's GCP in three ways:
#   1. Shared BQ datasets (LR writes approved query outputs into a project
#      the bank can read from).
#   2. GCS buckets (the "GCS Export" destination type we saw in the UI
#      drops CSV/Parquet files into a bucket).
#   3. Publisher-side pipeline (LR reads from FRB tables via a service
#      account; less relevant for our "read out" analysis goal).
#
# This script inventories what YOUR gcloud identity can see so we know
# whether we can query LiveRamp data programmatically instead of screen-
# scraping the UI.
#
# Usage:
#   bash scripts/discover_liveramp_gcp_connection.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired, re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired, re-logging in..."
    gcloud auth application-default login
fi

echo
echo "════════════════════════════════════════════════════════════"
echo "  LiveRamp x GCP connection discovery"
echo "  User: $(gcloud config get-value account 2>/dev/null)"
echo "════════════════════════════════════════════════════════════"


echo
echo "── 1. All GCP projects visible to you ──"
echo "Look for anything with 'liveramp', 'lr-', 'cleanroom', 'clean-room',"
echo "'pnp', 'picknpay', 'ebucks', 'ramp' or a partner-shared org."
gcloud projects list --format="table(projectId,name,projectNumber)" \
    --filter="NOT projectId~^sys-" 2>&1 | grep -viE '^ *$' | head -60


echo
echo "── 2. All BigQuery datasets you can see, grouped by project ──"
echo "LiveRamp usually lands data into datasets named 'lr_*', 'liveramp_*',"
echo "'clean_room_*', 'shared_*', or dedicated per-partner projects."
for proj in $(gcloud projects list --format='value(projectId)' \
    --filter='NOT projectId~^sys-' 2>/dev/null); do
    dsets=$(bq --project_id="$proj" --format=prettyjson ls --datasets \
        --max_results=100 2>/dev/null | grep -o '\"datasetId\": *\"[^\"]*\"' \
        | sed 's/.*: *\"//;s/\"$//' | sort -u)
    if [ -n "$dsets" ]; then
        echo
        echo "  Project: $proj"
        echo "$dsets" | sed 's/^/    /'
    fi
done


echo
echo "── 3. Focused BQ scan for LR-flavoured datasets ──"
echo "Any dataset name containing: liveramp | cleanroom | clean_room |"
echo "ramp | shared | partner | pnp | picknpay | ebucks | smartshopper"
for proj in $(gcloud projects list --format='value(projectId)' \
    --filter='NOT projectId~^sys-' 2>/dev/null); do
    hits=$(bq --project_id="$proj" ls --datasets --max_results=200 2>/dev/null \
        | tail -n +3 \
        | awk '{print $1}' \
        | grep -iE 'liveramp|cleanroom|clean_room|ramp|shared|partner|pnp|picknpay|ebucks|smartshopper|smart_shopper')
    if [ -n "$hits" ]; then
        echo
        echo "  Project: $proj"
        echo "$hits" | sed 's/^/    /'
    fi
done


echo
echo "── 4. GCS buckets you can list ──"
echo "LR 'GCS Export' destinations write CSV/Parquet here. Look for names"
echo "containing 'lr-', 'liveramp', 'cleanroom', 'ramp', 'pnp', 'ebucks'."
gcloud storage buckets list --format="value(name,location,project_number)" 2>&1 \
    | head -100


echo
echo "── 5. Focused GCS bucket scan ──"
gcloud storage buckets list --format='value(name)' 2>/dev/null \
    | grep -iE 'liveramp|cleanroom|clean-room|ramp|pnp|picknpay|ebucks|smartshopper|shared'


echo
echo "── 6. Recent objects in each candidate bucket ──"
echo "For each bucket matching the LR pattern, list the top-level folders"
echo "and the 10 most recent objects (to see the naming convention and"
echo "whether the export is still live)."
for b in $(gcloud storage buckets list --format='value(name)' 2>/dev/null \
    | grep -iE 'liveramp|cleanroom|ramp|pnp|picknpay|ebucks|smartshopper'); do
    echo
    echo "  gs://$b"
    echo "    -- top-level folders --"
    gcloud storage ls "gs://$b/" 2>/dev/null | head -10 | sed 's/^/    /'
    echo "    -- 10 most recent objects (any depth) --"
    gcloud storage ls --recursive "gs://$b/**" 2>/dev/null \
        | tail -10 | sed 's/^/    /'
done


echo
echo "── 7. Environment sniff for LiveRamp API creds ──"
echo "If FNB has already provisioned an LR API key/token, it's usually in"
echo "an env var, a JSON file in ~/.config, or a Secret Manager entry."
env | grep -iE 'liveramp|ramp|clean.?room' | grep -v PATH
ls -la ~/.config 2>/dev/null | grep -iE 'liveramp|ramp'
gcloud secrets list --format='value(name)' 2>/dev/null \
    | grep -iE 'liveramp|ramp|cleanroom' | head -10


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. What to look at:"
echo "  Sections 2/3: any BQ project or dataset named like LR?"
echo "  Sections 4/5/6: any GCS bucket that LR is writing exports to?"
echo "  Section 7:    any API cred already provisioned?"
echo ""
echo "  If Section 3 or Section 5 finds a hit, we can read the LR data"
echo "  programmatically with bq and gcloud storage. Otherwise the UI"
echo "  walkthrough (LIVERAMP_DISCOVERY_PLAYBOOK.md) is our path."
echo "════════════════════════════════════════════════════════════"
