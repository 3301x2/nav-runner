#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Load the Aspire Primelife Meta audience CSV into BigQuery + sense-check
#
# Source (sandbox only):  gs://testing-sandbox-123/ASPIRE_PRIMELIFE_20260706_FB.csv
# Target:                 <project>.staging.aspire_primelife_meta_audience
#
# Mode:
#   sandbox    → LOAD CSV from GCS into fmn-sandbox.staging.aspire_primelife_meta_audience
#                  + run every sense-check
#   production → COPY the sandbox table into fmn-production-462014.staging.aspire_primelife_meta_audience
#                  using `bq cp` (no CSV touch on prod side)
#                  + run every sense-check against the prod copy
#
# All columns loaded as STRING (safest for hashed identifiers). Retype
# later if the sense-check shows clean numeric / date fields.
#
# Usage:
#   bash scripts/load_aspire_audience.sh sandbox
#   bash scripts/load_aspire_audience.sh production
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

ENV="${1:-sandbox}"
case "$ENV" in
    sandbox|dev|sb)     ENV_KIND="sandbox";    PROJECT="fmn-sandbox"    ;;
    production|prod|prd) ENV_KIND="production"; PROJECT="fmn-production-462014" ;;
    *) echo "Usage: bash $0 [sandbox|production]"; exit 1 ;;
esac

SOURCE_URI="gs://testing-sandbox-123/ASPIRE_PRIMELIFE_20260706_FB.csv"
# TWO forms of the same table:
#   *_CLI  → project:dataset.table  (colon) — for `bq load`, `bq cp`, `bq show`
#   *_SQL  → project.dataset.table  (dots)  — for SQL queries in `bq query`
SANDBOX_TABLE_CLI="fmn-sandbox:staging.aspire_primelife_meta_audience"
SANDBOX_TABLE_SQL="fmn-sandbox.staging.aspire_primelife_meta_audience"
TABLE_CLI="${PROJECT}:staging.aspire_primelife_meta_audience"
TABLE_SQL="${PROJECT}.staging.aspire_primelife_meta_audience"

if ! gcloud auth print-access-token >/dev/null 2>&1; then
    echo "Auth token expired — re-logging in..."
    gcloud auth login
fi
if ! gcloud auth application-default print-access-token >/dev/null 2>&1; then
    echo "ADC token expired — re-logging in..."
    gcloud auth application-default login
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty --max_rows=50 "$1"
}

echo
echo "════════════════════════════════════════════════════════════"
echo "  ASPIRE PRIMELIFE Meta audience — $ENV_KIND"
echo "  Project: $PROJECT"
echo "  Target:  $TABLE_SQL"
if [ "$ENV_KIND" = "sandbox" ]; then
    echo "  Source:  $SOURCE_URI (CSV load)"
else
    echo "  Source:  $SANDBOX_TABLE_SQL (bq cp from sandbox)"
fi
echo "════════════════════════════════════════════════════════════"

# Ensure staging dataset exists — auto-create if missing (needs bigquery.user
# which is included in bigquery.dataEditor + up).
echo
echo "── Ensure staging dataset exists ──"
if bq --project_id="$PROJECT" show --dataset "${PROJECT}:staging" >/dev/null 2>&1; then
    echo "   ✓ ${PROJECT}.staging exists"
else
    echo "   • ${PROJECT}.staging not found — attempting to create it"
    if bq --project_id="$PROJECT" mk \
        --location=africa-south1 \
        --dataset \
        --description="Staging tables — audience loads etc" \
        "${PROJECT}:staging" 2>/tmp/mk_error.log; then
        echo "   ✓ Created ${PROJECT}.staging"
    else
        echo "   ✗ Could not create ${PROJECT}.staging"
        echo
        cat /tmp/mk_error.log 2>/dev/null | head -3
        echo
        echo "Ask Rory to run in Cloud Shell:"
        echo "    gcloud projects add-iam-policy-binding $PROJECT \\"
        echo "        --member=\"user:$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null | head -1)\" \\"
        echo "        --role=\"roles/bigquery.user\" \\"
        echo "        --condition=None"
        exit 1
    fi
fi

if [ "$ENV_KIND" = "sandbox" ]; then
    echo
    echo "── Peek at the CSV header first (so we can see the real column count) ──"
    HEADER=$(gcloud storage cat "$SOURCE_URI" 2>/dev/null | head -1 || true)
    if [ -n "$HEADER" ]; then
        HEADER_COL_COUNT=$(echo "$HEADER" | awk -F',' '{print NF}')
        echo "   Header ($HEADER_COL_COUNT columns): $HEADER"
    else
        echo "   (couldn't read header — proceeding anyway)"
        HEADER_COL_COUNT=0
    fi

    echo
    echo "── Loading CSV into $TABLE_SQL ──"
    echo "Explicit schema: all 18 columns as STRING (matches the header we peeked at)."
    # CSV has NULL bytes (ASCII 0) in some hashed values →
    # --preserve_ascii_control_characters tolerates them (row kept, not rejected).
    # Explicit schema so we KNOW the column names — autodetect renames them
    # unpredictably ("string_field_0" etc.), breaking downstream sense-checks.
    bq load \
        --project_id="$PROJECT" \
        --location=africa-south1 \
        --source_format=CSV \
        --replace \
        --skip_leading_rows=1 \
        --allow_quoted_newlines \
        --max_bad_records=5000 \
        --preserve_ascii_control_characters \
        --schema="email:STRING,email2:STRING,email3:STRING,phone:STRING,phone2:STRING,phone3:STRING,madid:STRING,fn:STRING,ln:STRING,zip:STRING,ct:STRING,st:STRING,country:STRING,dob:STRING,doby:STRING,gen:STRING,age:STRING,uid:STRING" \
        "$TABLE_CLI" \
        "$SOURCE_URI"

    LOAD_STATUS=$?
    if [ $LOAD_STATUS -ne 0 ]; then
        echo
        echo "Load failed. Diagnostic hints:"
        echo "  • Check that $TABLE_SQL dataset ($PROJECT.staging) exists — should"
        echo "    (we verified earlier)"
        echo "  • Verify bucket read: gcloud storage cat $SOURCE_URI | head -3"
        echo "  • If the CSV has non-UTF8 chars, add --encoding=ISO-8859-1"
        echo "  • If it's tab-separated, add --field_delimiter='\\t'"
        exit 1
    fi
else
    # Production: copy the already-sense-checked sandbox table into prod BQ.
    # `bq cp` works cross-project as long as your identity has:
    #   - bigquery.dataViewer (or higher) on fmn-sandbox
    #   - bigquery.dataEditor (or higher) on fmn-production-462014

    # Confirm the sandbox source exists before we try to copy it
    echo
    echo "── Verify sandbox source table exists ──"
    if bq --project_id=fmn-sandbox show "$SANDBOX_TABLE_CLI" >/dev/null 2>&1; then
        SANDBOX_ROWS=$(bq query --quiet --use_legacy_sql=false \
            --project_id=fmn-sandbox --format=csv \
            "SELECT COUNT(*) FROM \`$SANDBOX_TABLE_SQL\`" 2>/dev/null | tail -1)
        echo "   ✓ $SANDBOX_TABLE_SQL exists ($SANDBOX_ROWS rows)"
    else
        echo "   ✗ $SANDBOX_TABLE_SQL doesn't exist. Run sandbox mode first:"
        echo "       bash $0 sandbox"
        exit 1
    fi

    # Retry the copy — IAM grants take 1-3 minutes to propagate globally, and
    # `bq cp` sometimes fails on the first try even when the roles are in place.
    echo
    echo "── Copying sandbox table into prod ──"
    MAX_ATTEMPTS=4
    SLEEP_BETWEEN=15
    for attempt in $(seq 1 $MAX_ATTEMPTS); do
        echo "   Attempt $attempt of $MAX_ATTEMPTS..."
        if bq cp \
            --force \
            --location=africa-south1 \
            "$SANDBOX_TABLE_CLI" \
            "$TABLE_CLI" 2>/tmp/cp_error.log; then
            echo "   ✓ Copy succeeded on attempt $attempt"
            break
        fi
        if [ $attempt -eq $MAX_ATTEMPTS ]; then
            echo
            echo "   ✗ Copy failed after $MAX_ATTEMPTS attempts. Last error:"
            echo
            cat /tmp/cp_error.log 2>/dev/null | head -8
            echo
            echo "Common causes:"
            echo "  • IAM propagation still in flight — wait 2-3 min and rerun"
            echo "  • Missing roles/bigquery.dataViewer on fmn-sandbox"
            echo "  • Missing roles/bigquery.dataEditor on fmn-production-462014"
            echo "  • Region mismatch (both datasets must be in africa-south1)"
            exit 1
        fi
        echo "   Waiting ${SLEEP_BETWEEN}s before retry (IAM propagation)..."
        sleep $SLEEP_BETWEEN
    done

    # Post-copy sanity check — did the row counts match?
    echo
    echo "── Verifying prod table matches sandbox ──"
    PROD_ROWS=$(bq query --quiet --use_legacy_sql=false \
        --project_id="$PROJECT" --format=csv \
        "SELECT COUNT(*) FROM \`$TABLE_SQL\`" 2>/dev/null | tail -1)
    echo "   Sandbox: $SANDBOX_ROWS rows"
    echo "   Prod:    $PROD_ROWS rows"
    if [ "$SANDBOX_ROWS" = "$PROD_ROWS" ]; then
        echo "   ✓ Row counts match"
    else
        echo "   ✗ Row counts differ — investigate before using prod table"
        exit 1
    fi
fi

echo
echo "── Actual column names in the loaded table ──"
bq_q "
    SELECT column_name, data_type, ordinal_position
    FROM \`${PROJECT}\`.staging.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = 'aspire_primelife_meta_audience'
    ORDER BY ordinal_position
"

echo
echo "── Table loaded. Row count ──"
bq_q "SELECT COUNT(*) AS row_count FROM \`$TABLE_SQL\`"

echo
echo "══════════════ SENSE-CHECKS ═══════════════════════════════"

echo
echo "── 1. Null count per column ──"
bq_q "
    SELECT
        COUNTIF(email    IS NULL OR TRIM(email)    = '') AS null_email,
        COUNTIF(email2   IS NULL OR TRIM(email2)   = '') AS null_email2,
        COUNTIF(email3   IS NULL OR TRIM(email3)   = '') AS null_email3,
        COUNTIF(phone    IS NULL OR TRIM(phone)    = '') AS null_phone,
        COUNTIF(phone2   IS NULL OR TRIM(phone2)   = '') AS null_phone2,
        COUNTIF(phone3   IS NULL OR TRIM(phone3)   = '') AS null_phone3,
        COUNTIF(madid    IS NULL OR TRIM(madid)    = '') AS null_madid,
        COUNTIF(fn       IS NULL OR TRIM(fn)       = '') AS null_fn,
        COUNTIF(ln       IS NULL OR TRIM(ln)       = '') AS null_ln,
        COUNTIF(zip      IS NULL OR TRIM(zip)      = '') AS null_zip,
        COUNTIF(ct       IS NULL OR TRIM(ct)       = '') AS null_ct,
        COUNTIF(st       IS NULL OR TRIM(st)       = '') AS null_st,
        COUNTIF(country  IS NULL OR TRIM(country)  = '') AS null_country,
        COUNTIF(dob      IS NULL OR TRIM(dob)      = '') AS null_dob,
        COUNTIF(doby     IS NULL OR TRIM(doby)     = '') AS null_doby,
        COUNTIF(gen      IS NULL OR TRIM(gen)      = '') AS null_gen,
        COUNTIF(age      IS NULL OR TRIM(age)      = '') AS null_age,
        COUNTIF(uid      IS NULL OR TRIM(uid)      = '') AS null_uid
    FROM \`$TABLE_SQL\`
"

echo
echo "── 2. Distinct count per column ──"
echo "(spots columns that are all one value or all-null)"
bq_q "
    SELECT
        COUNT(DISTINCT email)   AS d_email,
        COUNT(DISTINCT email2)  AS d_email2,
        COUNT(DISTINCT email3)  AS d_email3,
        COUNT(DISTINCT phone)   AS d_phone,
        COUNT(DISTINCT phone2)  AS d_phone2,
        COUNT(DISTINCT phone3)  AS d_phone3,
        COUNT(DISTINCT madid)   AS d_madid,
        COUNT(DISTINCT fn)      AS d_fn,
        COUNT(DISTINCT ln)      AS d_ln,
        COUNT(DISTINCT zip)     AS d_zip,
        COUNT(DISTINCT ct)      AS d_ct,
        COUNT(DISTINCT st)      AS d_st,
        COUNT(DISTINCT country) AS d_country,
        COUNT(DISTINCT dob)     AS d_dob,
        COUNT(DISTINCT doby)    AS d_doby,
        COUNT(DISTINCT gen)     AS d_gen,
        COUNT(DISTINCT age)     AS d_age,
        COUNT(DISTINCT uid)     AS d_uid
    FROM \`$TABLE_SQL\`
"

echo
echo "── 3. Identifier presence — rows with NO usable identifier ──"
echo "(Meta rejects rows where email + phone + madid are all blank)"
bq_q "
    SELECT
        COUNTIF(
            (email  IS NULL OR TRIM(email)  = '') AND
            (email2 IS NULL OR TRIM(email2) = '') AND
            (email3 IS NULL OR TRIM(email3) = '') AND
            (phone  IS NULL OR TRIM(phone)  = '') AND
            (phone2 IS NULL OR TRIM(phone2) = '') AND
            (phone3 IS NULL OR TRIM(phone3) = '') AND
            (madid  IS NULL OR TRIM(madid)  = '')
        ) AS rows_with_no_identifier,
        COUNTIF(TRIM(COALESCE(email, ''))  != '') AS have_email,
        COUNTIF(TRIM(COALESCE(phone, ''))  != '') AS have_phone,
        COUNTIF(TRIM(COALESCE(madid, ''))  != '') AS have_madid,
        COUNTIF(TRIM(COALESCE(uid,   ''))  != '') AS have_uid,
        COUNT(*) AS total
    FROM \`$TABLE_SQL\`
"

echo
echo "── 4. Duplicate uid check ──"
bq_q "
    WITH uid_counts AS (
        SELECT uid, COUNT(*) AS n
        FROM \`$TABLE_SQL\`
        WHERE uid IS NOT NULL AND TRIM(uid) != ''
        GROUP BY uid
    )
    SELECT
        COUNT(*)                          AS distinct_uids,
        COUNTIF(n = 1)                    AS uids_appearing_once,
        COUNTIF(n > 1)                    AS uids_with_duplicates,
        MAX(n)                            AS max_duplicate_count
    FROM uid_counts
"

echo
echo "── 5. Email — length distribution + hash-shape hint ──"
echo "(SHA-256 hashed emails are exactly 64 hex chars; raw emails vary)"
bq_q "
    SELECT
        LENGTH(email) AS email_length,
        COUNT(*)      AS row_count
    FROM \`$TABLE_SQL\`
    WHERE email IS NOT NULL AND TRIM(email) != ''
    GROUP BY email_length
    ORDER BY row_count DESC
    LIMIT 20
"

echo
echo "── 6. Email hash-format compliance (64-hex-char check) ──"
bq_q "
    SELECT
        COUNTIF(REGEXP_CONTAINS(email, r'^[a-f0-9]{64}\$')) AS sha256_hex_lower,
        COUNTIF(REGEXP_CONTAINS(email, r'^[A-F0-9]{64}\$')) AS sha256_hex_upper,
        COUNTIF(REGEXP_CONTAINS(email, r'^[A-Fa-f0-9]{64}\$')) AS sha256_hex_any,
        COUNTIF(REGEXP_CONTAINS(email, r'@'))                AS looks_like_raw_email,
        COUNT(*)                                              AS total_non_null_email
    FROM \`$TABLE_SQL\`
    WHERE email IS NOT NULL AND TRIM(email) != ''
"

echo
echo "── 7. Phone — first-char distribution ──"
echo "(Meta expects E.164-ish digits; leading + or country code is fine)"
bq_q "
    SELECT
        SUBSTR(phone, 1, 3) AS first_3_chars,
        COUNT(*)            AS row_count
    FROM \`$TABLE_SQL\`
    WHERE phone IS NOT NULL AND TRIM(phone) != ''
    GROUP BY first_3_chars
    ORDER BY row_count DESC
    LIMIT 15
"

echo
echo "── 8. Phone hash-format compliance ──"
bq_q "
    SELECT
        COUNTIF(REGEXP_CONTAINS(phone, r'^[A-Fa-f0-9]{64}\$')) AS sha256_hex,
        COUNTIF(REGEXP_CONTAINS(phone, r'^[0-9]+\$'))          AS digits_only,
        COUNTIF(REGEXP_CONTAINS(phone, r'^\+[0-9]+\$'))         AS e164_with_plus,
        COUNT(*)                                                AS total_non_null_phone
    FROM \`$TABLE_SQL\`
    WHERE phone IS NOT NULL AND TRIM(phone) != ''
"

echo
echo "── 9. Gender distinct values ──"
bq_q "
    SELECT gen, COUNT(*) AS row_count
    FROM \`$TABLE_SQL\`
    WHERE gen IS NOT NULL AND TRIM(gen) != ''
    GROUP BY gen
    ORDER BY row_count DESC
    LIMIT 15
"

echo
echo "── 10. Country distinct values ──"
bq_q "
    SELECT country, COUNT(*) AS row_count
    FROM \`$TABLE_SQL\`
    WHERE country IS NOT NULL AND TRIM(country) != ''
    GROUP BY country
    ORDER BY row_count DESC
    LIMIT 15
"

echo
echo "── 11. Age — numeric range ──"
bq_q "
    SELECT
        MIN(SAFE_CAST(age AS INT64))                                AS min_age,
        MAX(SAFE_CAST(age AS INT64))                                AS max_age,
        ROUND(AVG(SAFE_CAST(age AS INT64)), 1)                      AS avg_age,
        COUNTIF(SAFE_CAST(age AS INT64) IS NULL AND TRIM(COALESCE(age,'')) != '') AS non_numeric_age
    FROM \`$TABLE_SQL\`
"

echo
echo "── 12. Year-of-birth (doby) — range ──"
bq_q "
    SELECT
        MIN(SAFE_CAST(doby AS INT64))                                AS min_year,
        MAX(SAFE_CAST(doby AS INT64))                                AS max_year,
        COUNTIF(SAFE_CAST(doby AS INT64) IS NULL AND TRIM(COALESCE(doby,'')) != '') AS non_numeric_doby
    FROM \`$TABLE_SQL\`
"

echo
echo "── 13. DOB parseability ──"
bq_q "
    SELECT
        COUNTIF(SAFE.PARSE_DATE('%Y-%m-%d', dob) IS NOT NULL)              AS parses_iso,
        COUNTIF(SAFE.PARSE_DATE('%Y%m%d',   dob) IS NOT NULL)              AS parses_yyyymmdd,
        COUNTIF(SAFE.PARSE_DATE('%d/%m/%Y', dob) IS NOT NULL)              AS parses_ddmmyyyy,
        COUNTIF(REGEXP_CONTAINS(dob, r'^[A-Fa-f0-9]{64}\$'))                AS looks_hashed,
        COUNTIF(dob IS NULL OR TRIM(dob) = '')                              AS null_or_blank,
        COUNT(*)                                                            AS total
    FROM \`$TABLE_SQL\`
"

echo
echo "── 14. First 5 rows (sample) ──"
bq_q "SELECT * FROM \`$TABLE_SQL\` LIMIT 5"

echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Load-and-check complete for $TABLE_SQL"
echo
echo "  Next steps if numbers look good:"
echo "  1. Retype columns after inspection (e.g. age → INT64 if all"
echo "     numeric, doby → INT64, dob → DATE if parseable)"
echo "  2. If you're on sandbox and want to promote to prod, run:"
echo "       bash $0 production"
echo "     (does bq cp from this sandbox table to fmn-production-462014)"
echo "════════════════════════════════════════════════════════════"
