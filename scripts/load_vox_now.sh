#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Load THIS Vox audience file into sandbox + promote to prod. No flags.
#
# Source:   gs://incoming_vox/VOX_CONSENT_InclusionA_20260706_FB.csv
# Table:    vox_consent_inclusiona_meta_audience (auto-derived)
# Expected: ~130,000 rows
#
# Usage:
#   bash scripts/load_vox_now.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

exec bash "$SCRIPT_DIR/load_fb_audience_all.sh" \
    --source gs://incoming_vox/VOX_CONSENT_InclusionA_20260706_FB.csv \
    --expected-rows 130000
