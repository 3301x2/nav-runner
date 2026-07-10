#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Load THIS PnP Payday inclusion file into sandbox + promote to prod.
# No flags needed — same shape as load_vox_now.sh and load_aspire_audience.sh.
#
# Source:  gs://testing-sandbox-123/payday_pnp_inclusionA_20260709_FB.csv
# Sandbox: fmn-sandbox.staging.payday_pnp_inclusiona_meta_audience
# Prod:    fmn-production-462014.staging.payday_pnp_inclusiona_meta_audience
#
# Usage:
#   bash scripts/load_payday_now.sh
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

exec bash "$SCRIPT_DIR/load_fb_audience_all.sh" \
    --source gs://testing-sandbox-123/payday_pnp_inclusionA_20260709_FB.csv
