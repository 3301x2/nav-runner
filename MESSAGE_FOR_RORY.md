# Message to send Rory

**Subject:** Access commands — 6 gcloud lines + 2 CREATE SCHEMA statements

---

Hi Rory,

Sorry — my last SQL was wrong. BigQuery's `GRANT` only works at the dataset level, not project level. Rewrote everything correctly. Should take about 2 minutes total.

**All the commands are in the repo:**

```
nav-runner/queries/rory_grant_prosper_bq_access.sql
```

**What's in it:**

**Part 1 — Cloud Shell (6 lines total, 3 per project):**
Grants me `bigquery.user` + `bigquery.dataEditor` + `storage.objectViewer` at the project level on both `fmn-sandbox` and `fmn-production`. That's the full BQ + GCS read/write access I need to load audience CSVs from any bucket in either project.

**Part 2 — BigQuery console (2 statements):**
`CREATE SCHEMA IF NOT EXISTS ... staging` in each project. This is the piece that was missing — `bigquery.dataEditor` alone doesn't include `bigquery.datasets.create`, hence the "Dataset not found" error last time.

**Part 3 — Verify (queries at the bottom of the file):**
Confirms the schemas exist and the IAM grants stuck.

**One thing to swap:** just search-replace `<PROSPER_EMAIL>` with my actual email before running.

Thanks again for the help — appreciate it,
Prosper
