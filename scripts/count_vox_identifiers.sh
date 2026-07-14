#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# How many usable emails and phone numbers are in the Vox audience table?
# Shows the actual schema FIRST — the previous version assumed column names
# that don't exist in this table (autodetect renamed them to string_field_0
# etc.), which made every COUNTIF return garbage.
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

PROJECT="fmn-production-462014"
DATASET="staging"
TABLE_NAME="vox_consent_inclusiona_meta_audience"
TABLE_SQL="${PROJECT}.${DATASET}.${TABLE_NAME}"

# Auto-refresh both user and ADC creds if either is dead
if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired — re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired — re-logging in..."
    gcloud auth application-default login
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
        --format=pretty --max_rows=30 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  Vox audience — identifier counts"
echo "  Table: $TABLE_SQL"
echo "════════════════════════════════════════════════════════════"


# ── 1. Show the actual schema first ──
echo
echo "── 1. Actual column names in this table ──"
bq_q "
    SELECT column_name, data_type, ordinal_position
    FROM \`${PROJECT}.${DATASET}.INFORMATION_SCHEMA.COLUMNS\`
    WHERE table_name = '$TABLE_NAME'
    ORDER BY ordinal_position
"


# ── 2. Row count (this always works) ──
echo
echo "── 2. Total row count ──"
bq_q "SELECT COUNT(*) AS total_rows FROM \`$TABLE_SQL\`"


# ── 3. First 2 rows sample (see what values actually look like) ──
echo
echo "── 3. Sample of first 2 rows ──"
bq_q "SELECT * FROM \`$TABLE_SQL\` LIMIT 2"


# ── 4. Try the standard FB-schema counts (will error if columns differ) ──
echo
echo "── 4. Standard 18-col FB schema counts (may error) ──"
bq_q "
    SELECT
        COUNT(*)                                                  AS total_rows,
        COUNTIF(TRIM(COALESCE(email,  '')) != '')                  AS with_email,
        COUNTIF(TRIM(COALESCE(email2, '')) != '')                  AS with_email2,
        COUNTIF(TRIM(COALESCE(email3, '')) != '')                  AS with_email3,
        COUNTIF(TRIM(COALESCE(phone,  '')) != '')                  AS with_phone,
        COUNTIF(TRIM(COALESCE(phone2, '')) != '')                  AS with_phone2,
        COUNTIF(TRIM(COALESCE(phone3, '')) != '')                  AS with_phone3,
        COUNT(DISTINCT email)                                     AS distinct_emails,
        COUNT(DISTINCT phone)                                     AS distinct_phones
    FROM \`$TABLE_SQL\`
" || echo "   (query errored — the table doesn't have email/phone columns by those names; see Section 1)"


echo
echo "════════════════════════════════════════════════════════════"
echo "  If Section 4 errored, the table columns are named differently."
echo "  Read Section 1 to see the actual column names, then Prosper"
echo "  can update the count query to use those names."
echo "════════════════════════════════════════════════════════════"
