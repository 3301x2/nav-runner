# nav-runner

Lightweight runner scripts.

## Usage

Each script in `scripts/` is self-contained and queries BigQuery via `gcloud auth`. No project state lives here — outputs go to the working directory.

```bash
bash scripts/discover_adidas.sh production
bash scripts/discover_superbalist.sh production
```

## Requirements

- `gcloud` CLI authenticated (`gcloud auth login --update-adc`)
- `bq` CLI installed
- Read access to the relevant GCP project
