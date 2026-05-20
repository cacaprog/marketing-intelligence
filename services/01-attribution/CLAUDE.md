# Media Attribution Service

## What this service computes

Seven multi-touch attribution models (6 heuristics + 1 LightGBM data-driven) applied to
B2B SaaS touchpoint data, benchmarked against causal ground truth, with ROAS and a
budget allocation recommendation computed for all paid channels.

## Inputs

Reads from `data/raw/b2b_attribution.db` (read-only):
- `touchpoints` — attribution spine
- `opportunities` (filter: `is_won = 1`) — revenue basis; `created_date` used for train/test split
- `channel_spend` — weekly spend for ROAS and allocation
- `leads` — for CPQL computation

## Outputs

Written to `data/processed/01-attribution/`:
- `attribution_results.parquet/csv` — channel × model revenue table (42 rows: 7 channels × 6 heuristics)
- `benchmark_results.parquet/csv` — MAE + Pearson r vs. ground truth, ranked 1–7 (all 7 models)
- `roas_results.parquet/csv` — ROAS, CPQL, CPO for 5 paid channels × 7 models (35 rows)
- `ml_attribution_results.parquet/csv` — data-driven model channel revenue (7 rows, test set only)
- `feature_importance.parquet/csv` — 8 features ranked by LightGBM gain importance
- `allocation_recommendations.parquet/csv` — per-channel budget split (5 paid channels)
- `models/attribution_lgbm.joblib` — serialized model artifact (encoder + booster)
- `models/attribution_lgbm.txt` — LightGBM booster in human-readable text format (audit copy)

## Run batch

```bash
python services/01-attribution/main.py
# Optional: --output-dir PATH      (default: data/processed/01-attribution/)
# Optional: --budget-brl FLOAT     (default: sum of historical channel_spend)
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
| data_driven | models/data_driven.py | LightGBM regression on 8 features; trained on opps before 2024-03-01; evaluated on test set |

## Temporal split (data-driven model only)

- Train: `opp.created_date < 2024-03-01` (~14 months)
- Test: `opp.created_date >= 2024-03-01` (~4 months)
- `TRAIN_CUTOFF_DATE` is defined in `shared/config.py`
- Benchmark MAE for data_driven is computed on the **test set only** — honest out-of-sample evaluation

## Key invariant

All models must satisfy `weight.groupby('opp_id').sum() == 1.0 (±1e-9)` — verified by
`tests/test_models.py` and `tests/test_trainer.py`.
