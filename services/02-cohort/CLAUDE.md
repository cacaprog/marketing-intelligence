# CLAUDE.md — Cohort Analysis Service

## What this service computes

Groups the 7,962 B2B leads into 18 monthly acquisition cohorts (2023-01 → 2024-06)
and computes:
1. **Cohort revenue** — cumulative closed-won ACV at fixed windows (1, 3, 6, 9, 12 months) per cohort
2. **Cohort funnel** — lead → MQL → opp → closed-won counts and conversion rates per cohort
3. **Channel cohorts** — revenue + funnel metrics segmented by `first_touch_channel` per cohort

Key invariant: cells where the window has not yet elapsed are `NULL + is_observable=False`,
not zero. Zero means zero revenue in an observable window.

## Inputs

- `data/raw/b2b_attribution.db` (read-only) — tables: `leads`, `opportunities`
- Shared helpers: `shared/db.get_cohort_data()`, `shared/config.COHORT_WINDOWS`, `shared/config.DATASET_REFERENCE_DATE`

## Outputs

Written to `data/processed/02-cohort/` (created at runtime, gitignored):
- `cohort_revenue.parquet` + `cohort_revenue.csv`
- `cohort_funnel.parquet` + `cohort_funnel.csv`
- `cohort_by_channel.parquet` + `cohort_by_channel.csv`

## Commands

```bash
# Run pipeline (writes all parquets + CSVs)
python services/02-cohort/main.py

# Launch dashboard (requires pipeline to have run first)
streamlit run services/02-cohort/dashboard/app.py

# Run tests
python -m pytest services/02-cohort/tests/ -v

# Run a single test module
python -m pytest services/02-cohort/tests/test_cohort_revenue.py -v
```

## Window arithmetic

Window W uses a half-open interval: `close_date in [cohort_start, cohort_start + DateOffset(months=W))`.
Do NOT use `timedelta(days=30*W)` — it gives wrong results at month boundaries.

## sys.path pattern

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from shared.db import get_cohort_data
from shared.config import COHORT_WINDOWS, DATASET_REFERENCE_DATE
```
