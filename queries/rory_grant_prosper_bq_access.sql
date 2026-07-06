-- ═════════════════════════════════════════════════════════════════════
-- For Rory to run in the BigQuery console
--
-- Grants Prosper full BigQuery + GCS read access on both fmn-sandbox
-- and fmn-production so he can load audience CSVs from ANY bucket into
-- BQ and copy tables between the two projects.
--
-- Replace `PROSPER@example.com` with Prosper's actual email before running.
--
-- HOW TO RUN:
--   1. Open BQ console → set project to fmn-sandbox
--   2. Paste + run the sandbox block
--   3. Switch project to fmn-production
--   4. Paste + run the production block
--   5. Also run the staging-dataset-create blocks in each project
--
-- Notes:
--   • roles/bigquery.user includes bigquery.datasets.create (needed to
--     create the `staging` dataset — this was the missing piece last time)
--   • roles/bigquery.dataEditor lets Prosper read/write data in datasets
--   • roles/storage.objectViewer at the PROJECT level = read on every
--     bucket in the project (not just testing-sandbox-123)
--
-- Grants are idempotent — safe to re-run.
-- ═════════════════════════════════════════════════════════════════════


-- ─── PROJECT: fmn-sandbox ──────────────────────────────────────────
-- Set project to fmn-sandbox in the BQ console, then run these:

GRANT `roles/bigquery.user`
  ON PROJECT `fmn-sandbox`
  TO "user:PROSPER@example.com";

GRANT `roles/bigquery.dataEditor`
  ON PROJECT `fmn-sandbox`
  TO "user:PROSPER@example.com";

-- Create staging dataset (needed for the audience load)
CREATE SCHEMA IF NOT EXISTS `fmn-sandbox.staging`
OPTIONS (
  location = "africa-south1",
  description = "Staging tables — audience loads etc"
);


-- ─── PROJECT: fmn-production ───────────────────────────────────────
-- Switch project to fmn-production in the BQ console, then run these:

GRANT `roles/bigquery.user`
  ON PROJECT `fmn-production`
  TO "user:PROSPER@example.com";

GRANT `roles/bigquery.dataEditor`
  ON PROJECT `fmn-production`
  TO "user:PROSPER@example.com";

CREATE SCHEMA IF NOT EXISTS `fmn-production.staging`
OPTIONS (
  location = "africa-south1",
  description = "Staging tables — audience loads etc"
);


-- ═════════════════════════════════════════════════════════════════════
-- GCS BUCKET ACCESS — cannot be granted from BigQuery SQL.
-- Rory must run these in Cloud Shell or terminal:
--
--   gcloud projects add-iam-policy-binding fmn-sandbox \
--       --member="user:PROSPER@example.com" \
--       --role="roles/storage.objectViewer"
--
--   gcloud projects add-iam-policy-binding fmn-production \
--       --member="user:PROSPER@example.com" \
--       --role="roles/storage.objectViewer"
--
-- This grants read on EVERY bucket in each project — no more per-bucket
-- grants needed for future audience files.
-- ═════════════════════════════════════════════════════════════════════


-- ─── OPTIONAL: verify what Prosper now has ─────────────────────────
-- Rory can run these to confirm the grants stuck:

SELECT * FROM `fmn-sandbox.region-africa-south1.INFORMATION_SCHEMA.OBJECT_PRIVILEGES`
WHERE grantee = 'user:PROSPER@example.com'
ORDER BY object_name;

SELECT * FROM `fmn-production.region-africa-south1.INFORMATION_SCHEMA.OBJECT_PRIVILEGES`
WHERE grantee = 'user:PROSPER@example.com'
ORDER BY object_name;
