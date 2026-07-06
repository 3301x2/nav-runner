#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# One-command wrapper: load an FB audience CSV into sandbox, then copy
# it to prod, running sense-checks against both. Halts at the first
# failure so you never promote a bad file.
#
# Usage:
#   bash scripts/load_fb_audience_all.sh \\
#       --source gs://incoming_vox/VOX_CONSENT_InclusionA_20260706_FB.csv \\
#       --expected-rows 130000
#
# Optional:
#   --table <name>          override auto-derived name
#   --tolerance-pct <n>     override the ±5% row-count tolerance
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)

echo
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  FB Audience — Sandbox load + Prod promote in one shot   ║"
echo "╚═══════════════════════════════════════════════════════════╝"

echo
echo "── Step 1: Load to sandbox ──"
if ! bash "$SCRIPT_DIR/load_fb_audience.sh" "$@" --env sandbox; then
    echo
    echo "✗ Sandbox load failed. Not promoting to prod."
    exit 1
fi

echo
echo "── Step 2: Promote to prod ──"
if ! bash "$SCRIPT_DIR/load_fb_audience.sh" "$@" --env production; then
    echo
    echo "✗ Prod promotion failed. Sandbox is loaded but prod is not."
    exit 1
fi

echo
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║  ✓ All done — table live in sandbox AND prod              ║"
echo "╚═══════════════════════════════════════════════════════════╝"
