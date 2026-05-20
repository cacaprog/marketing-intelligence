# Media Attribution Service

## What this service computes

Six multi-touch attribution models applied to B2B SaaS touchpoint data, benchmarked
against causal ground truth, with ROAS computed for all paid channels.

## Inputs

Reads from `data/raw/b2b_attribution.db` (read-only):
- `touchpoints` — attribution spine
- `opportunities` (filter: `is_won = 1`) — revenue basis
- `channel_spend` — weekly spend for ROAS
- `leads` — for CPQL computation

## Outputs

Written to `data/processed/01-attribution/`:
- `attribution_results.parquet/csv` — channel × model revenue table (42 rows: 7 channels × 6 models)
- `benchmark_results.parquet/csv` — MAE + Pearson correlation vs. ground truth, ranked 1–6
- `roas_results.parquet/csv` — ROAS, CPQL, CPO for 5 paid channels × 6 models (30 rows)

## Run batch

```bash
python services/01-attribution/main.py
# Optional: --output-dir PATH  (default: data/processed/01-attribution/)
```

## Run dashboard

```bash
streamlit run services/01-attribution/dashboard/app.py
# Open http://localhost:8501
# Requires batch outputs to exist first
```

## Run tests

```bash
pytest services/01-attribution/tests/ -v
```

## Model registry

| Model | File | Key logic |
|-------|------|-----------|
| last_touch | models/last_touch.py | 100% to is_last_touch=1 |
| first_touch | models/first_touch.py | 100% to is_first_touch=1 |
| linear | models/linear.py | 1/n per touch |
| time_decay | models/time_decay.py | exp(-days/14) normalized; 14-day half-life from shared/config.py |
| position_based | models/position_based.py | 40/20/40 (1-touch=100%, 2-touch=50/50) |
| engagement_weighted | models/engagement_weighted.py | engagement_score/sum(scores) per opp |
| ground_truth | models/ground_truth.py | true_marginal_contribution (benchmark baseline only) |

## Key invariant

All models must satisfy `weight.groupby('opp_id').sum() == 1.0 (±1e-9)` — verified by
`tests/test_models.py::test_weights_sum_to_one_per_opp`.
