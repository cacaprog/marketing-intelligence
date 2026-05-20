# Implementation Plan: Media Attribution Model

**Branch**: `001-media-attribution` | **Date**: 2026-05-20 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `specs/001-media-attribution/spec.md`

## Summary

Build `services/01-attribution/` — a Python service that applies six multi-touch
attribution models (last-touch, first-touch, linear, time-decay, position-based,
engagement-weighted) to the B2B SaaS dataset, benchmarks each model against the
causal ground truth (`true_marginal_contribution`), computes ROAS per paid channel,
and exposes results via a local Streamlit dashboard.

## Technical Context

**Language/Version**: Python 3.11

**Primary Dependencies**: pandas, numpy, scipy (Pearson correlation), streamlit,
plotly (via shared/viz.py), sqlite3 (stdlib)

**Storage**: SQLite read (`data/raw/b2b_attribution.db`) → Parquet + CSV write
(`data/processed/01-attribution/`)

**Testing**: pytest

**Target Platform**: Local development machine (Linux/macOS)

**Project Type**: Data-science service + local web dashboard

**Performance Goals**: All six models complete in < 30 seconds on a standard laptop
(~6K touchpoints, ~1.4K opportunities)

**Constraints**: Read-only access to `data/raw/`; no auth; single-user local use only

**Scale/Scope**: ~6,363 touchpoints, ~1,410 opportunities, 7 channels, 1 analyst

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|---------|
| I. Service Independence | ✅ PASS | Lives entirely in `services/01-attribution/`; zero imports from other services |
| II. Dataset Immutability | ✅ PASS | Reads from `data/raw/`; writes only to `data/processed/01-attribution/` |
| III. Shared Code First | ✅ PASS | DB connection via `shared/db.py`; config constants in `shared/config.py`; charts via `shared/viz.py` |
| IV. Ground Truth Accountability | ✅ PASS | FR-003 and US2 mandate benchmark table (MAE + Pearson) vs. `true_marginal_contribution` |
| V. Subpopulation Awareness | ✅ PASS | Aggregations are at channel level; flat channel totals are an intentional design choice for MVP; segmented ROAS by industry/size deferred to v2 and flagged in docs |

**Post-design re-check**: All five principles confirmed. No violations to justify.

## Project Structure

### Documentation (this feature)

```text
specs/001-media-attribution/
├── plan.md              ← this file
├── research.md          ← Phase 0 output
├── data-model.md        ← Phase 1 output
├── quickstart.md        ← Phase 1 output
├── contracts/
│   └── module-interfaces.md   ← Phase 1 output
└── tasks.md             ← Phase 2 output (/speckit-tasks)
```

### Source Code

```text
services/01-attribution/
├── CLAUDE.md
├── main.py                        # CLI entry point; runs all models and writes outputs
├── models/
│   ├── last_touch.py              # compute(spine) → spine + weight
│   ├── first_touch.py
│   ├── linear.py
│   ├── time_decay.py              # uses TIME_DECAY_HALF_LIFE from shared/config.py
│   ├── position_based.py          # 40/20/40 split
│   ├── engagement_weighted.py     # weight = engagement_score / sum per opp
│   └── ground_truth.py            # extracts true_marginal_contribution as "model"
├── analysis/
│   ├── compare_models.py          # run_all_models(); to_channel_table()
│   ├── roas_calculator.py         # compute_roas()
│   └── benchmark.py               # benchmark_models() → MAE + Pearson rank table
├── dashboard/
│   └── app.py                     # streamlit run → model selector + charts
└── tests/
    ├── test_models.py             # revenue conservation invariant per model
    ├── test_benchmark.py          # benchmark output shape and ranking monotonicity
    └── test_roas.py               # ROAS only for paid channels; formula correctness

shared/
├── db.py          # get_attribution_spine(), get_channel_spend(), get_leads()
├── config.py      # TIME_DECAY_HALF_LIFE = 14; DB_PATH; PROCESSED_DIR
└── viz.py         # standard Plotly theme

data/
├── raw/
│   └── b2b_attribution.db        # read-only source of truth
└── processed/
    └── 01-attribution/            # all outputs written here
        ├── attribution_results.parquet
        ├── attribution_results.csv
        ├── benchmark_results.parquet
        ├── benchmark_results.csv
        ├── roas_results.parquet
        └── roas_results.csv
```

**Structure Decision**: Single-service layout under `services/01-attribution/`
following the monorepo convention from CLAUDE.md. Shared infrastructure uses the
existing `shared/` layer. No separate backend/frontend split needed — Streamlit
serves both computation trigger and UI.

## Complexity Tracking

No constitution violations. Table omitted.
