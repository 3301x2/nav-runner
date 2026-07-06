-- ═════════════════════════════════════════════════════════════════════
-- For Rory — grant Prosper access to load Aspire audience CSV
--
-- IMPORTANT: BigQuery's GRANT statement ONLY works at the schema/dataset
-- level, NOT at the project level. Project-level IAM grants must be done
-- via `gcloud` in Cloud Shell.
--
-- Below is a mix:
--   • Project-level roles → gcloud commands (Cloud Shell)
--   • Dataset creation    → BigQuery SQL (paste into console)
--
-- Replace ndwakhulu.sikhwari@nav.co.za with Prosper's real email in ALL the commands.
-- ═════════════════════════════════════════════════════════════════════


-- ────────────────────────────────────────────────────────────────────
-- PART 1 — RUN IN CLOUD SHELL (gcloud, not BQ SQL)
-- These grant Prosper project-level BQ + GCS access on both projects.
-- ────────────────────────────────────────────────────────────────────

/*

# ── SANDBOX ───────────────────────────────────────────────────────
gcloud projects add-iam-policy-binding fmn-sandbox \
    --member="user:ndwakhulu.sikhwari@nav.co.za" \
    --role="roles/bigquery.user" \
    --condition=None

gcloud projects add-iam-policy-binding fmn-sandbox \
    --member="user:ndwakhulu.sikhwari@nav.co.za" \
    --role="roles/bigquery.dataEditor" \
    --condition=None

gcloud projects add-iam-policy-binding fmn-sandbox \
    --member="user:ndwakhulu.sikhwari@nav.co.za" \
    --role="roles/storage.objectViewer" \
    --condition=None


# ── PRODUCTION ────────────────────────────────────────────────────
gcloud projects add-iam-policy-binding fmn-production \
    --member="user:ndwakhulu.sikhwari@nav.co.za" \
    --role="roles/bigquery.user" \
    --condition=None

gcloud projects add-iam-policy-binding fmn-production \
    --member="user:ndwakhulu.sikhwari@nav.co.za" \
    --role="roles/bigquery.dataEditor" \
    --condition=None

gcloud projects add-iam-policy-binding fmn-production \
    --member="user:ndwakhulu.sikhwari@nav.co.za" \
    --role="roles/storage.objectViewer" \
    --condition=None

*/


-- ────────────────────────────────────────────────────────────────────
-- PART 2 — RUN IN BIGQUERY CONSOLE
-- Create the staging datasets in both projects.
-- ────────────────────────────────────────────────────────────────────

-- Set project to fmn-sandbox in the BQ console, then run:
CREATE SCHEMA IF NOT EXISTS `fmn-sandbox.staging`
OPTIONS (
  location = "africa-south1",
  description = "Staging tables — audience loads etc"
);


-- Switch project to fmn-production in the BQ console, then run:
CREATE SCHEMA IF NOT EXISTS `fmn-production.staging`
OPTIONS (
  location = "africa-south1",
  description = "Staging tables — audience loads etc"
);


-- ────────────────────────────────────────────────────────────────────
-- PART 3 — VERIFY (BigQuery console)
-- Confirm the datasets were created and Prosper can see them.
-- ────────────────────────────────────────────────────────────────────

-- List all datasets in each project (should show `staging`):
SELECT schema_name, location
FROM `fmn-sandbox.INFORMATION_SCHEMA.SCHEMATA`
ORDER BY schema_name;

SELECT schema_name, location
FROM `fmn-production.INFORMATION_SCHEMA.SCHEMATA`
ORDER BY schema_name;


-- ────────────────────────────────────────────────────────────────────
-- PART 4 — VERIFY IAM (Cloud Shell, gcloud)
-- Confirm the roles Prosper now has on each project.
-- ────────────────────────────────────────────────────────────────────

/*

gcloud projects get-iam-policy fmn-sandbox \
    --flatten="bindings[].members" \
    --filter="bindings.members:ndwakhulu.sikhwari@nav.co.za" \
    --format="value(bindings.role)"

gcloud projects get-iam-policy fmn-production \
    --flatten="bindings[].members" \
    --filter="bindings.members:ndwakhulu.sikhwari@nav.co.za" \
    --format="value(bindings.role)"

# Expected output for each project (3 lines):
#   roles/bigquery.dataEditor
#   roles/bigquery.user
#   roles/storage.objectViewer

*/
