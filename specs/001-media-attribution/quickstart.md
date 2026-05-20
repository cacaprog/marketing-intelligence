# Quickstart: Media Attribution Service

## Prerequisites

- `uv` installed system-wide
- Dataset generated: `data/raw/b2b_attribution.db` exists
  (run `python generate_dataset.py` from repo root if not)

## Setup

```bash
uv sync
```

## Run Attribution (batch)

```bash
python services/01-attribution/main.py
```

Outputs written to `data/processed/01-attribution/`:
- `attribution_results.parquet` + `attribution_results.csv`
- `benchmark_results.parquet` + `benchmark_results.csv`
- `roas_results.parquet` + `roas_results.csv`

## Launch Dashboard

```bash
streamlit run services/01-attribution/dashboard/app.py
```

Open http://localhost:8501 in your browser.

## Run Tests

```bash
python -m pytest services/01-attribution/tests/ -v
```

## Validate Outputs

After running the batch, verify revenue conservation:

```python
import pandas as pd

df = pd.read_parquet("data/processed/01-attribution/attribution_results.parquet")
totals = df.groupby("model_name")["attributed_revenue_brl"].sum()
print(totals)  # All six models should show the same total (Closed Won ACV)
```
