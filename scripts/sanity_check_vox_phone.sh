#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Sanity-check the Vox `phone` column — is it actually phone-shaped
# (SHA-256 hash of a phone number) or has it been duplicated from email?
#
# Meta CA files hash identifiers with SHA-256 (64 hex chars). If email
# and phone are identical per-row, phone was populated from email — bad.
#
# Usage:
#   bash scripts/sanity_check_vox_phone.sh [sandbox|production]
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-production}"
case "$ENV" in
    sandbox|dev|sb)         PROJECT="fmn-sandbox" ;;
    production|prod|prd)    PROJECT="fmn-production-462014" ;;
    *) echo "Usage: bash $0 [sandbox|production]"; exit 1 ;;
esac

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired — re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired — re-logging in..."
    gcloud auth application-default login
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --location=africa-south1 --format=pretty --max_rows=30 "$1"
}

TABLE="\`$PROJECT.staging.vox_consent_inclusiona_meta_audience\`"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Vox phone sanity check"
echo "  Project: $PROJECT"
echo "════════════════════════════════════════════════════════════"

echo
echo "── 1. Email vs phone — same value per row? ──"
echo "If rows_with_email_eq_phone ≈ total_rows → phone column was copied"
echo "from email (bad). If ~0 → phone is genuinely a separate identifier."
bq_q "
    SELECT
        COUNT(*)                                       AS total_rows,
        COUNTIF(email = phone)                         AS rows_with_email_eq_phone,
        COUNTIF(email IS NOT NULL AND phone IS NOT NULL AND email != phone)
                                                       AS rows_with_email_ne_phone,
        ROUND(100.0 * COUNTIF(email = phone) / COUNT(*), 2)
                                                       AS pct_email_eq_phone
    FROM $TABLE
"

echo
echo "── 2. Distinct phones and distinct emails ──"
echo "If distinct_phones is close to distinct_emails → both are unique identifiers"
echo "If distinct_phones == distinct_emails EXACTLY → strong signal phone = email"
bq_q "
    SELECT
        COUNT(DISTINCT email)  AS distinct_emails,
        COUNT(DISTINCT phone)  AS distinct_phones
    FROM $TABLE
"

echo
echo "── 3. Sample: 5 rows side-by-side (first 12 chars of each hash) ──"
echo "Visually compare — if email prefix != phone prefix, they're different values"
bq_q "
    SELECT
        SUBSTR(email, 1, 12) AS email_prefix,
        SUBSTR(phone, 1, 12) AS phone_prefix,
        LENGTH(email)        AS email_len,
        LENGTH(phone)        AS phone_len
    FROM $TABLE
    LIMIT 5
"

echo
echo "── 4. Hash shape check ──"
echo "Meta CA identifiers are SHA-256 → 64 hex characters."
echo "If lengths ≠ 64 or contain non-hex chars, formatting is off."
bq_q "
    SELECT
        COUNTIF(LENGTH(email) = 64)                                     AS emails_64_chars,
        COUNTIF(LENGTH(phone) = 64)                                     AS phones_64_chars,
        COUNTIF(REGEXP_CONTAINS(email, r'^[0-9a-f]{64}\$'))              AS emails_valid_sha256,
        COUNTIF(REGEXP_CONTAINS(phone, r'^[0-9a-f]{64}\$'))              AS phones_valid_sha256,
        COUNT(*)                                                        AS total_rows
    FROM $TABLE
"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Read Section 1 first — that's the definitive answer."
echo "  If pct_email_eq_phone ≈ 100%: phone column is unusable (=email)"
echo "  If pct_email_eq_phone ≈ 0%: phone is a genuine separate identifier"
echo "════════════════════════════════════════════════════════════"
