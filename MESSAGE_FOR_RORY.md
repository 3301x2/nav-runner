# Message to send Rory

**Subject:** BQ access — SQL you can paste + one gcloud step for GCS

---

Hi Rory,

Thanks for the editor grant — I'm still hitting `Dataset fmn-sandbox:staging not found` because dataset-create needs `bigquery.user` (not included in `bigquery.dataEditor`).

I've put together the exact SQL for you to paste into BQ so we can move faster. It's in the repo:

```
nav-runner/queries/rory_grant_prosper_bq_access.sql
```

**What's in it:**

1. **In BQ console (paste and run):** grants me `bigquery.user` + `bigquery.dataEditor` on both `fmn-sandbox` and `fmn-production`, and creates the `staging` dataset in both projects.

2. **In terminal / Cloud Shell (one command per project):** grants me `storage.objectViewer` at the **project level** so I can read any bucket in each project — no more per-bucket grants needed for future audience files.

```
gcloud projects add-iam-policy-binding fmn-sandbox \
    --member="user:<my-email>" \
    --role="roles/storage.objectViewer"

gcloud projects add-iam-policy-binding fmn-production \
    --member="user:<my-email>" \
    --role="roles/storage.objectViewer"
```

Just replace `PROSPER@example.com` in the SQL and `<my-email>` in the gcloud commands with my actual email.

Verification queries are at the bottom of the file so you can confirm the grants stuck.

Once done, IAM takes 1-3 minutes to propagate — I'll re-auth and retry.

Thanks a lot, appreciate the help,
Prosper
