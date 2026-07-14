#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# How many usable emails and phone numbers are in the Vox audience table?
# Runs against the prod table (fmn-production-462014).
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROJECT="fmn-production-462014"
TABLE_SQL="fmn-production-462014.staging.vox_consent_inclusiona_meta_audience"

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
        --format=pretty --max_rows=20 "$1" 2>/dev/null
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Vox audience — identifier counts"
echo "  Table: $TABLE_SQL"
echo "════════════════════════════════════════════════════════════"


echo
echo "── Total rows + identifier availability ──"
bq_q "
    SELECT
        COUNT(*)                                                            AS total_rows,
        COUNTIF(TRIM(COALESCE(email,  '')) != '')                            AS with_email,
        COUNTIF(TRIM(COALESCE(email2, '')) != '')                            AS with_email2,
        COUNTIF(TRIM(COALESCE(email3, '')) != '')                            AS with_email3,
        COUNTIF(TRIM(COALESCE(phone,  '')) != '')                            AS with_phone,
        COUNTIF(TRIM(COALESCE(phone2, '')) != '')                            AS with_phone2,
        COUNTIF(TRIM(COALESCE(phone3, '')) != '')                            AS with_phone3
    FROM \`$TABLE_SQL\`
"


echo
echo "── Distinct hashed identifiers (unique emails / phones) ──"
bq_q "
    SELECT
        COUNT(DISTINCT email)  AS distinct_emails,
        COUNT(DISTINCT phone)  AS distinct_phones
    FROM \`$TABLE_SQL\`
    WHERE TRIM(COALESCE(email, '')) != '' OR TRIM(COALESCE(phone, '')) != ''
"


echo
echo "── Rows with at least one usable email or phone ──"
bq_q "
    SELECT
        COUNT(*) AS rows_with_at_least_one_identifier
    FROM \`$TABLE_SQL\`
    WHERE TRIM(COALESCE(email,  '')) != ''
       OR TRIM(COALESCE(email2, '')) != ''
       OR TRIM(COALESCE(email3, '')) != ''
       OR TRIM(COALESCE(phone,  '')) != ''
       OR TRIM(COALESCE(phone2, '')) != ''
       OR TRIM(COALESCE(phone3, '')) != ''
"
