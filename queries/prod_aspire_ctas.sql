-- ═════════════════════════════════════════════════════════════════════
-- Copy the Aspire audience table from sandbox → prod via CTAS
--
-- WHY this instead of `bq cp`:
--   • bq cp needs serviceusage.services.use on prod (which we don't have)
--   • BQ Studio in the console handles quota differently, so a CTAS query
--     works even without that permission
--
-- HOW to run:
--   1. Open BQ Studio: https://console.cloud.google.com/bigquery?project=fmn-production-462814
--   2. Make sure the project selector at the top shows FMN - Production
--   3. Paste the block below and click RUN
--   4. Then paste + run the verification block
-- ═════════════════════════════════════════════════════════════════════


-- ─── Step 1: create the staging dataset in prod if it doesn't exist ──
CREATE SCHEMA IF NOT EXISTS `fmn-production-462814.staging`
OPTIONS (
  location    = "africa-south1",
  description = "Staging tables — audience loads etc"
);


-- ─── Step 2: create the aspire table as SELECT from sandbox ──────────
-- This runs in prod, reads sandbox as a cross-project source.
CREATE OR REPLACE TABLE `fmn-production-462814.staging.aspire_primelife_meta_audience`
AS
SELECT *
FROM `fmn-sandbox.staging.aspire_primelife_meta_audience`;


-- ─── Step 3: verify the copy landed intact ───────────────────────────
SELECT
    (SELECT COUNT(*) FROM `fmn-sandbox.staging.aspire_primelife_meta_audience`)             AS sandbox_row_count,
    (SELECT COUNT(*) FROM `fmn-production-462814.staging.aspire_primelife_meta_audience`)  AS prod_row_count,
    (SELECT COUNT(*) FROM `fmn-sandbox.staging.aspire_primelife_meta_audience`)
      - (SELECT COUNT(*) FROM `fmn-production-462814.staging.aspire_primelife_meta_audience`)
                                                                                            AS delta;
-- Expected: sandbox = prod = 1,576,827, delta = 0


-- ─── Step 4: quick sense-check on the prod copy ──────────────────────
SELECT
    COUNT(*)                                                      AS total_rows,
    COUNT(DISTINCT uid)                                           AS distinct_uids,
    COUNTIF(REGEXP_CONTAINS(email, r'^[A-Fa-f0-9]{64}$'))         AS valid_sha256_emails,
    COUNTIF(REGEXP_CONTAINS(phone, r'^[A-Fa-f0-9]{64}$'))         AS valid_sha256_phones,
    COUNTIF(
        (email IS NULL OR TRIM(email) = '') AND
        (phone IS NULL OR TRIM(phone) = '') AND
        (madid IS NULL OR TRIM(madid) = '')
    )                                                             AS rows_with_no_identifier
FROM `fmn-production-462814.staging.aspire_primelife_meta_audience`;
-- Expected: total_rows and distinct_uids both = 1,576,827
--           valid_sha256_emails and valid_sha256_phones both = 1,576,827
--           rows_with_no_identifier = 0
