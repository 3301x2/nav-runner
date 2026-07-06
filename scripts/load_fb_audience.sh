#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────
# Generic loader for FB / Meta Custom Audience CSVs → BigQuery
#
# Replaces the audience-specific loaders. One script, any FB-format file.
# Auto-derives the table name from the CSV filename. Auto-creates the
# staging dataset if missing. Runs 14 sense-checks after load.
#
# Standard FB Custom Audience schema (18 STRING columns):
#   email, email2, email3, phone, phone2, phone3, madid,
#   fn, ln, zip, ct, st, country, dob, doby, gen, age, uid
#
# Usage:
#   Sandbox load with expected-rows check:
#     bash scripts/load_fb_audience.sh \\
#         --source gs://incoming_vox/VOX_CONSENT_InclusionA_20260706_FB.csv \\
#         --expected-rows 130000
#
#   Promote to prod (copies sandbox table to prod BQ):
#     bash scripts/load_fb_audience.sh \\
#         --source gs://incoming_vox/VOX_CONSENT_InclusionA_20260706_FB.csv \\
#         --env production
#
#   Override target table name (default is auto-derived from filename):
#     bash scripts/load_fb_audience.sh \\
#         --source gs://bucket/file.csv \\
#         --table my_custom_name
#
# Auto-derivation:
#   VOX_CONSENT_InclusionA_20260706_FB.csv →
#     vox_consent_inclusiona_meta_audience
#   ASPIRE_PRIMELIFE_20260706_FB.csv →
#     aspire_primelife_meta_audience
# ─────────────────────────────────────────────────────────────────────────

set -uo pipefail

# ── Argument parsing ─────────────────────────────────────────────────
SOURCE_URI=""
ENV_KIND="sandbox"
DATASET="staging"
TABLE_NAME="auto"
EXPECTED_ROWS=""
ROW_TOLERANCE_PCT=5   # warn if actual differs from expected by > 5%

while [ $# -gt 0 ]; do
    case "$1" in
        --source)          SOURCE_URI="$2";      shift 2 ;;
        --env)             ENV_KIND="$2";        shift 2 ;;
        --dataset)         DATASET="$2";         shift 2 ;;
        --table)           TABLE_NAME="$2";      shift 2 ;;
        --expected-rows)   EXPECTED_ROWS="$2";   shift 2 ;;
        --tolerance-pct)   ROW_TOLERANCE_PCT="$2"; shift 2 ;;
        -h|--help)
            grep '^# ' "$0" | sed 's/^# //' | head -35
            exit 0 ;;
        *)
            echo "Unknown argument: $1"
            echo "Run with --help for usage"
            exit 1 ;;
    esac
done

if [ -z "$SOURCE_URI" ]; then
    echo "ERROR: --source is required"
    echo "  Example: --source gs://incoming_vox/VOX_CONSENT_InclusionA_20260706_FB.csv"
    exit 1
fi

case "$ENV_KIND" in
    sandbox|dev|sb)      ENV_KIND="sandbox";    PROJECT="fmn-sandbox"           ;;
    production|prod|prd) ENV_KIND="production"; PROJECT="fmn-production-462014" ;;
    *) echo "ERROR: --env must be sandbox or production"; exit 1 ;;
esac


# ── Auto-derive the table name from the CSV filename ─────────────────
# Rules:
#   1. Strip path + .csv extension
#   2. Strip trailing date (8 digits, possibly with underscores)
#   3. Strip _FB / _fb / _meta suffix
#   4. Lowercase, replace non-alphanumeric with _
#   5. Collapse multiple underscores
#   6. Append _meta_audience if not already ending in _audience
if [ "$TABLE_NAME" = "auto" ]; then
    FILENAME=$(basename "$SOURCE_URI" .csv)
    # strip date-like patterns (8 digits with optional underscores around)
    DERIVED=$(echo "$FILENAME" | \
        sed -E 's/_?[0-9]{8}//g' | \
        sed -E 's/_(FB|fb|META|meta)$//' | \
        tr '[:upper:]' '[:lower:]' | \
        sed -E 's/[^a-z0-9]+/_/g' | \
        sed -E 's/__+/_/g' | \
        sed -E 's/^_|_$//g')
    if [[ ! "$DERIVED" =~ _audience$ ]]; then
        DERIVED="${DERIVED}_meta_audience"
    fi
    TABLE_NAME="$DERIVED"
fi

TABLE_CLI="${PROJECT}:${DATASET}.${TABLE_NAME}"
TABLE_SQL="${PROJECT}.${DATASET}.${TABLE_NAME}"
SANDBOX_TABLE_CLI="fmn-sandbox:${DATASET}.${TABLE_NAME}"
SANDBOX_TABLE_SQL="fmn-sandbox.${DATASET}.${TABLE_NAME}"


# ── Auth check ───────────────────────────────────────────────────────
if ! gcloud auth print-access-token >/dev/null 2>&1; then
    gcloud auth login --update-adc --quiet || exit 1
fi

bq_q() {
    bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" --format=pretty --max_rows=50 "$1" 2>/dev/null
}


echo
echo "════════════════════════════════════════════════════════════"
echo "  FB Audience loader — $ENV_KIND"
echo "════════════════════════════════════════════════════════════"
echo "  Project:  $PROJECT"
echo "  Source:   $SOURCE_URI"
echo "  Target:   $TABLE_SQL"
if [ -n "$EXPECTED_ROWS" ]; then
    echo "  Expected: ~$EXPECTED_ROWS rows (±${ROW_TOLERANCE_PCT}% tolerance)"
fi
echo "════════════════════════════════════════════════════════════"


# ── Ensure staging dataset exists ────────────────────────────────────
echo
echo "── Ensure ${PROJECT}:${DATASET} dataset exists ──"
if bq --project_id="$PROJECT" show --dataset "${PROJECT}:${DATASET}" >/dev/null 2>&1; then
    echo "   ✓ ${PROJECT}:${DATASET} exists"
else
    echo "   • Not found — creating"
    if bq --project_id="$PROJECT" mk \
        --location=africa-south1 --dataset \
        --description="Staging tables — audience loads etc" \
        "${PROJECT}:${DATASET}" 2>/tmp/mk_error.log; then
        echo "   ✓ Created ${PROJECT}:${DATASET}"
    else
        echo "   ✗ Could not create ${PROJECT}:${DATASET}"
        cat /tmp/mk_error.log 2>/dev/null | head -3
        exit 1
    fi
fi


# ── Load path: sandbox loads from CSV; prod copies sandbox table ────
if [ "$ENV_KIND" = "sandbox" ]; then
    echo
    echo "── Peek at the CSV header ──"
    HEADER=$(gcloud storage cat "$SOURCE_URI" 2>/dev/null | head -1 || true)
    if [ -n "$HEADER" ]; then
        HEADER_COL_COUNT=$(echo "$HEADER" | awk -F',' '{print NF}')
        echo "   Header ($HEADER_COL_COUNT columns): $HEADER"
    else
        echo "   (couldn't read header — proceeding anyway)"
        HEADER_COL_COUNT=0
    fi

    # Use explicit 18-column FB schema if header matches; otherwise autodetect
    STANDARD_SCHEMA="email:STRING,email2:STRING,email3:STRING,phone:STRING,phone2:STRING,phone3:STRING,madid:STRING,fn:STRING,ln:STRING,zip:STRING,ct:STRING,st:STRING,country:STRING,dob:STRING,doby:STRING,gen:STRING,age:STRING,uid:STRING"

    echo
    echo "── Loading CSV into $TABLE_SQL ──"
    if [ "$HEADER_COL_COUNT" = "18" ]; then
        echo "   Using standard 18-column FB schema (all STRING)"
        SCHEMA_ARG="--schema=$STANDARD_SCHEMA"
    else
        echo "   ⚠ Header has $HEADER_COL_COUNT columns (expected 18) — using --autodetect"
        SCHEMA_ARG="--autodetect"
    fi

    bq load \
        --project_id="$PROJECT" \
        --location=africa-south1 \
        --source_format=CSV \
        --replace \
        --skip_leading_rows=1 \
        --allow_quoted_newlines \
        --max_bad_records=5000 \
        --preserve_ascii_control_characters \
        $SCHEMA_ARG \
        "$TABLE_CLI" \
        "$SOURCE_URI"

    if [ $? -ne 0 ]; then
        echo
        echo "Load failed. Common causes:"
        echo "  • Bucket read permission (${SOURCE_URI%/*})"
        echo "  • Schema mismatch — the CSV isn't the standard 18-column FB shape"
        echo "  • CSV corruption / encoding issue"
        exit 1
    fi
else
    # Production: cross-project copy of the already-verified sandbox table
    echo
    echo "── Verify sandbox source table exists ──"
    if bq --project_id=fmn-sandbox show "$SANDBOX_TABLE_CLI" >/dev/null 2>&1; then
        SANDBOX_ROWS=$(bq query --quiet --use_legacy_sql=false \
            --project_id=fmn-sandbox --format=csv \
            "SELECT COUNT(*) FROM \`$SANDBOX_TABLE_SQL\`" 2>/dev/null | tail -1)
        echo "   ✓ $SANDBOX_TABLE_SQL exists ($SANDBOX_ROWS rows)"
    else
        echo "   ✗ $SANDBOX_TABLE_SQL doesn't exist. Load to sandbox first:"
        echo "       bash $0 --source $SOURCE_URI"
        exit 1
    fi

    echo
    echo "── Copying sandbox → prod ──"
    MAX_ATTEMPTS=4
    for attempt in $(seq 1 $MAX_ATTEMPTS); do
        echo "   Attempt $attempt of $MAX_ATTEMPTS..."
        if bq cp --force --location=africa-south1 \
            "$SANDBOX_TABLE_CLI" "$TABLE_CLI" 2>/tmp/cp_error.log; then
            echo "   ✓ Copy succeeded on attempt $attempt"
            break
        fi
        if [ $attempt -eq $MAX_ATTEMPTS ]; then
            echo "   ✗ Copy failed after $MAX_ATTEMPTS attempts"
            cat /tmp/cp_error.log 2>/dev/null | head -8
            exit 1
        fi
        echo "   Waiting 15s before retry..."
        sleep 15
    done

    PROD_ROWS=$(bq query --quiet --use_legacy_sql=false \
        --project_id="$PROJECT" --format=csv \
        "SELECT COUNT(*) FROM \`$TABLE_SQL\`" 2>/dev/null | tail -1)
    echo "   Sandbox: $SANDBOX_ROWS rows"
    echo "   Prod:    $PROD_ROWS rows"
    if [ "$SANDBOX_ROWS" = "$PROD_ROWS" ]; then
        echo "   ✓ Row counts match"
    else
        echo "   ✗ Row counts differ"
        exit 1
    fi
fi


# ── Row-count expectation check ──────────────────────────────────────
ACTUAL_ROWS=$(bq query --quiet --use_legacy_sql=false --project_id="$PROJECT" \
    --format=csv "SELECT COUNT(*) FROM \`$TABLE_SQL\`" 2>/dev/null | tail -1)
echo
echo "── Row count: $ACTUAL_ROWS ──"

if [ -n "$EXPECTED_ROWS" ]; then
    DELTA_PCT=$(python3 -c "
actual = $ACTUAL_ROWS
expected = $EXPECTED_ROWS
if expected == 0:
    print('0')
else:
    print(round(abs(actual - expected) / expected * 100, 2))
" 2>/dev/null)
    echo "   Expected: $EXPECTED_ROWS (tolerance ±${ROW_TOLERANCE_PCT}%)"
    echo "   Actual:   $ACTUAL_ROWS"
    echo "   Delta:    ${DELTA_PCT}%"
    if python3 -c "exit(0 if $DELTA_PCT <= $ROW_TOLERANCE_PCT else 1)" 2>/dev/null; then
        echo "   ✓ Within tolerance"
    else
        echo "   ⚠ OUTSIDE TOLERANCE — check with uploader before using this file"
    fi
fi


# ── Column-schema summary ────────────────────────────────────────────
echo
echo "── Loaded table schema ──"
bq_q "
    SELECT column_name, data_type, ordinal_position
    FROM \`${PROJECT}\`.${DATASET}.INFORMATION_SCHEMA.COLUMNS
    WHERE table_name = '$TABLE_NAME'
    ORDER BY ordinal_position
"


echo
echo "══════════════ SENSE-CHECKS ═══════════════════════════════"

# Only run FB-specific checks if the standard schema was used
STANDARD_MODE=false
if [ "${HEADER_COL_COUNT:-0}" = "18" ] || [ "$ENV_KIND" = "production" ]; then
    STANDARD_MODE=true
fi

if [ "$STANDARD_MODE" = "true" ]; then
    echo
    echo "── 1. Identifier presence — rows with NO usable identifier ──"
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
            )                                                       AS rows_with_no_identifier,
            COUNTIF(TRIM(COALESCE(email, ''))  != '')                AS have_email,
            COUNTIF(TRIM(COALESCE(phone, ''))  != '')                AS have_phone,
            COUNTIF(TRIM(COALESCE(madid, ''))  != '')                AS have_madid,
            COUNTIF(TRIM(COALESCE(uid,   ''))  != '')                AS have_uid,
            COUNT(*)                                                 AS total
        FROM \`$TABLE_SQL\`
    "

    echo
    echo "── 2. Duplicate uid check ──"
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
    echo "── 3. Email hash-format compliance (64-hex-char check) ──"
    bq_q "
        SELECT
            COUNTIF(REGEXP_CONTAINS(email, r'^[A-Fa-f0-9]{64}\$')) AS sha256_hex,
            COUNTIF(REGEXP_CONTAINS(email, r'@'))                  AS looks_like_raw_email,
            COUNT(*)                                                AS total_non_null_email
        FROM \`$TABLE_SQL\`
        WHERE email IS NOT NULL AND TRIM(email) != ''
    "

    echo
    echo "── 4. Phone hash-format compliance ──"
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
    echo "── 5. Null count per column ──"
    bq_q "
        SELECT
            COUNTIF(email    IS NULL OR TRIM(email)    = '') AS null_email,
            COUNTIF(email2   IS NULL OR TRIM(email2)   = '') AS null_email2,
            COUNTIF(phone    IS NULL OR TRIM(phone)    = '') AS null_phone,
            COUNTIF(madid    IS NULL OR TRIM(madid)    = '') AS null_madid,
            COUNTIF(fn       IS NULL OR TRIM(fn)       = '') AS null_fn,
            COUNTIF(ln       IS NULL OR TRIM(ln)       = '') AS null_ln,
            COUNTIF(zip      IS NULL OR TRIM(zip)      = '') AS null_zip,
            COUNTIF(country  IS NULL OR TRIM(country)  = '') AS null_country,
            COUNTIF(dob      IS NULL OR TRIM(dob)      = '') AS null_dob,
            COUNTIF(gen      IS NULL OR TRIM(gen)      = '') AS null_gen,
            COUNTIF(age      IS NULL OR TRIM(age)      = '') AS null_age,
            COUNTIF(uid      IS NULL OR TRIM(uid)      = '') AS null_uid
        FROM \`$TABLE_SQL\`
    "
else
    echo
    echo "   ⚠ Non-standard schema detected — skipping FB-specific sense-checks."
    echo "   Investigate the header column names above and adapt as needed."
fi

echo
echo "── First 5 rows (sample) ──"
bq_q "SELECT * FROM \`$TABLE_SQL\` LIMIT 5"


echo
echo "════════════════════════════════════════════════════════════"
echo "  Done. Table $TABLE_SQL is loaded."
echo
if [ "$ENV_KIND" = "sandbox" ]; then
    echo "  Next: if numbers look good, promote to prod:"
    echo "    bash $0 --source $SOURCE_URI --env production"
else
    echo "  Table is now live in prod. Ready for LiveRamp / Meta activation."
fi
echo "════════════════════════════════════════════════════════════"
