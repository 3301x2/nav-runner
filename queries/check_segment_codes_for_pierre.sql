-- ─────────────────────────────────────────────────────────────────────────
-- Purpose: Show Pierre all coded segment values so he can confirm which
-- column maps to FNB's wealth-tier hierarchy (Entry Wallet → RMB).
--
-- Pierre asked "are you sure they are FL's?" — these queries surface every
-- segmentation column at once so he can spot the right one.
--
-- Run in BigQuery console against fmn-sandbox.
-- Copy the screenshot of each result and send via WhatsApp.
-- ─────────────────────────────────────────────────────────────────────────


-- ── Query 1: income_segment values (what Pierre's currently questioning) ──
SELECT
    income_segment AS code,
    COUNT(*) AS customers,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct
FROM `fmn-sandbox.staging.stg_customers`
GROUP BY income_segment
ORDER BY customers DESC;


-- ── Query 2: ALL coded segment columns at once ──
-- If Query 1's codes look wrong to Pierre, this shows every other column
-- so he can spot which one IS the right wealth-tier source.
SELECT 'gender'            AS column_name, CAST(gender            AS STRING) AS value, COUNT(*) AS customers
FROM `fmn-sandbox.staging.stg_customers` GROUP BY value
UNION ALL
SELECT 'income_segment'    AS column_name,                 income_segment        AS value, COUNT(*) AS customers
FROM `fmn-sandbox.staging.stg_customers` GROUP BY value
UNION ALL
SELECT 'hyper_segment'     AS column_name,                 hyper_segment         AS value, COUNT(*) AS customers
FROM `fmn-sandbox.staging.stg_customers` GROUP BY value
UNION ALL
SELECT 'main_banked'       AS column_name, CAST(main_banked       AS STRING) AS value, COUNT(*) AS customers
FROM `fmn-sandbox.staging.stg_customers` GROUP BY value
UNION ALL
SELECT 'credit_risk_class' AS column_name,                 credit_risk_class     AS value, COUNT(*) AS customers
FROM `fmn-sandbox.staging.stg_customers` GROUP BY value
UNION ALL
SELECT 'income_group'      AS column_name,                 income_group          AS value, COUNT(*) AS customers
FROM `fmn-sandbox.staging.stg_customers` GROUP BY value
ORDER BY column_name, customers DESC;


-- ── Query 3: full schema of base_data ──
-- If none of the staging columns match, Pierre may be remembering a column
-- from base_data that didn't survive into stg_customers.
SELECT column_name, data_type
FROM `fmn-sandbox.customer_spend.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'base_data'
ORDER BY ordinal_position;
