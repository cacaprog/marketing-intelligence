---
description: "Task list for Media Attribution Model — service 01-attribution"
---

# Tasks: Media Attribution Model

**Input**: Design documents from `specs/001-media-attribution/`

**Prerequisites**: plan.md ✅ | spec.md ✅ | research.md ✅ | data-model.md ✅ | contracts/ ✅

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Parallelizable — different files, no unmet dependencies
- **[Story]**: US1–US4 maps to user stories from spec.md

---

## Phase 1: Setup

**Purpose**: Directory structure and project initialization

- [x] T001 Create `services/01-attribution/` directory structure per plan.md (models/, analysis/, dashboard/, tests/)
- [x] T002 Add `streamlit`, `plotly`, `scipy` to `pyproject.toml` dependencies and run `uv sync`
- [x] T003 [P] Create `data/processed/01-attribution/` output directory; add it to `.gitignore`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared infrastructure that all user story tasks depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Implement `shared/config.py` — define `DB_PATH`, `TIME_DECAY_HALF_LIFE = 14`, `PROCESSED_DIR` constants
- [x] T005 [P] Implement `shared/db.py` — add `get_attribution_spine()` (joined touchpoints + won opportunities), `get_channel_spend()`, and `get_leads()` query helpers using sqlite3
- [x] T006 [P] Implement `shared/viz.py` — define standard Plotly theme (color palette, font, layout defaults) to be used by all service charts

**Checkpoint**: Foundation ready — all six model files and analysis modules can now be implemented in parallel

---

## Phase 3: User Story 1 — Compare Attribution Models (Priority: P1) 🎯 MVP

**Goal**: Produce six channel × revenue attribution tables from the touchpoints spine

**Independent Test**: `python services/01-attribution/main.py` completes without error and writes six model entries to `data/processed/01-attribution/attribution_results.parquet`; total revenue is identical across all six models

- [x] T007 [P] [US1] Implement `services/01-attribution/models/last_touch.py` — `compute(spine)` assigns all weight to the touchpoint where `is_last_touch == 1` per opp
- [x] T008 [P] [US1] Implement `services/01-attribution/models/first_touch.py` — `compute(spine)` assigns all weight to touchpoint where `is_first_touch == 1` per opp
- [x] T009 [P] [US1] Implement `services/01-attribution/models/linear.py` — `compute(spine)` assigns `weight = 1 / total_touches_in_journey` uniformly per opp
- [x] T010 [P] [US1] Implement `services/01-attribution/models/time_decay.py` — `compute(spine)` assigns `weight = exp(-days_before_opp_creation / TIME_DECAY_HALF_LIFE)` normalized per opp; import `TIME_DECAY_HALF_LIFE` from `shared/config.py`
- [x] T011 [P] [US1] Implement `services/01-attribution/models/position_based.py` — `compute(spine)` assigns 40% to first touch, 40% to last touch, 20% equally split among middle touches per opp
- [x] T012 [P] [US1] Implement `services/01-attribution/models/engagement_weighted.py` — `compute(spine)` assigns `weight = engagement_score / sum(engagement_score)` per opp
- [x] T013 [US1] Implement `services/01-attribution/analysis/compare_models.py` — `run_all_models(spine)` calls all six `compute()` functions and returns `dict[str, DataFrame]`; `to_channel_table(weighted_spine, model_name)` aggregates to `list[AttributionResult]` with revenue, opp count, and share_pct (depends on T007–T012)
- [x] T014 [US1] Implement `services/01-attribution/tests/test_models.py` — test that for each of the six models the `weight` column sums to 1.0 per opp_id (±1e-9 tolerance) and total attributed revenue equals total Closed Won ACV (depends on T007–T013)
- [x] T015 [US1] Implement `services/01-attribution/main.py` — CLI entry point with `--output-dir` flag; loads spine via `shared/db.py`; calls `run_all_models()`; writes `attribution_results.parquet` and `attribution_results.csv` to output dir (depends on T013)

**Checkpoint**: US1 is complete when `python services/01-attribution/main.py` produces `attribution_results.parquet` with rows for all six models and all channels, and `pytest services/01-attribution/tests/test_models.py` passes

---

## Phase 4: User Story 2 — Ground Truth Benchmark (Priority: P2)

**Goal**: Rank all six models by accuracy vs. `true_marginal_contribution`

**Independent Test**: `attribution_results.parquet` and `benchmark_results.parquet` both exist after running main.py; benchmark table has exactly six rows with monotonically ordered ranks

- [x] T016 [US2] Implement `services/01-attribution/models/ground_truth.py` — `compute(spine)` returns the spine with `weight = true_marginal_contribution` (no normalization needed; it already sums to 1.0 per opp)
- [x] T017 [US2] Implement `services/01-attribution/analysis/benchmark.py` — `benchmark_models(model_results, ground_truth)` computes MAE and Pearson correlation at channel-level share for each of the six models vs. ground truth; returns `list[BenchmarkResult]` sorted by MAE ascending with rank 1–6 (depends on T013, T016)
- [x] T018 [US2] Update `services/01-attribution/main.py` — add benchmark step: call `benchmark_models()` and write `benchmark_results.parquet` + `benchmark_results.csv` to output dir (depends on T015, T017)
- [x] T019 [US2] Implement `services/01-attribution/tests/test_benchmark.py` — test that output has exactly six rows, ranks are unique integers 1–6, and the row with rank 1 has the lowest MAE (depends on T017)

**Checkpoint**: US2 is complete when `benchmark_results.parquet` contains six rows ranked 1–6 and `pytest services/01-attribution/tests/test_benchmark.py` passes

---

## Phase 5: User Story 3 — ROAS by Channel (Priority: P3)

**Goal**: Compute ROAS, CPQL, and CPO for all five paid channels under each model

**Independent Test**: `roas_results.parquet` exists after running main.py; contains rows only for `paid_search`, `linkedin_ads`, `meta_ads`, `email_marketing`, `webinar_evento`; `roas = attributed_revenue_brl / total_spend_brl` for every row

- [x] T020 [US3] Implement `services/01-attribution/analysis/roas_calculator.py` — `compute_roas(attribution_results, spend_df, leads_df, opps_df)` joins each model's channel revenue with aggregated `spend_brl` from `channel_spend`; excludes channels where `spend_brl == 0`; computes `roas`, `cpql = spend / qualified_leads`, `cpo = spend / won_opps`; returns `list[RoasResult]`
- [x] T021 [US3] Update `services/01-attribution/main.py` — add ROAS step: call `compute_roas()` for each model and write `roas_results.parquet` + `roas_results.csv` to output dir (depends on T018, T020)
- [x] T022 [US3] Implement `services/01-attribution/tests/test_roas.py` — test that only paid channels appear in output, that `roas == attributed_revenue_brl / total_spend_brl` (±1e-6 tolerance), and that `organic_search` and `direct` are absent (depends on T020)

**Checkpoint**: US3 is complete when `roas_results.parquet` has rows only for paid channels and `pytest services/01-attribution/tests/test_roas.py` passes

---

## Phase 6: User Story 4 — Interactive Dashboard (Priority: P4)

**Goal**: Streamlit web app for no-code model exploration

**Independent Test**: `streamlit run services/01-attribution/dashboard/app.py` starts without error; selecting each of the six models from the dropdown updates the bar chart and ROAS table; benchmark section is visible without scrolling

- [x] T023 [US4] Implement `services/01-attribution/dashboard/app.py` — Streamlit app that loads the three parquet files from `data/processed/01-attribution/`; renders: (1) model selectbox, (2) horizontal bar chart of channel vs. attributed_revenue_brl using `shared/viz.py` theme, (3) benchmark table sorted by rank ascending, (4) ROAS table filtered to selected model (depends on T021)
- [x] T024 [US4] Smoke-test dashboard — run `streamlit run services/01-attribution/dashboard/app.py` locally; verify model switching updates charts and benchmark table is visible without scrolling on a 1280×800 viewport

**Checkpoint**: US4 is complete when all four sections render correctly for all six model selections

---

## Phase 7: Polish & Cross-Cutting Concerns

- [x] T025 [P] Write `services/01-attribution/CLAUDE.md` — document: what the service computes, inputs (`data/raw/b2b_attribution.db`), outputs (`data/processed/01-attribution/`), how to run batch and dashboard
- [x] T026 [P] Run quickstart.md revenue-conservation validation script and confirm all six model totals match
- [x] T027 Run full test suite `pytest services/01-attribution/tests/ -v` and fix any failures before marking service complete

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately
- **Foundational (Phase 2)**: Depends on Phase 1 — **BLOCKS all user stories**
- **US1 (Phase 3)**: Depends on Foundational; T007–T012 can all run in parallel; T013 depends on T007–T012; T015 depends on T013
- **US2 (Phase 4)**: Depends on US1 completion (T015); T016 can run in parallel with US1 after T004–T006
- **US3 (Phase 5)**: Depends on US2 completion (T018)
- **US4 (Phase 6)**: Depends on US3 completion (T021)
- **Polish (Phase 7)**: Depends on all user stories complete

### Within User Story 1 (parallel opportunities)

```bash
# All six model files can be written simultaneously:
T007  services/01-attribution/models/last_touch.py
T008  services/01-attribution/models/first_touch.py
T009  services/01-attribution/models/linear.py
T010  services/01-attribution/models/time_decay.py
T011  services/01-attribution/models/position_based.py
T012  services/01-attribution/models/engagement_weighted.py

# Then, once all six complete:
T013  services/01-attribution/analysis/compare_models.py
T014  services/01-attribution/tests/test_models.py  ← can be parallel with T013
```

### Foundational phase (parallel)

```bash
T004  shared/config.py
T005  shared/db.py       ← parallel with T004
T006  shared/viz.py      ← parallel with T004
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (**CRITICAL — blocks all stories**)
3. Complete Phase 3: US1 (six models + CLI output)
4. **STOP and VALIDATE**: `python services/01-attribution/main.py` + `pytest` pass
5. Revenue conservation confirmed via quickstart.md script

### Incremental Delivery

1. Setup + Foundational → shared layer ready
2. US1 → six attribution tables + CLI (**MVP**)
3. US2 → add benchmark ranking
4. US3 → add ROAS per paid channel
5. US4 → add Streamlit dashboard
6. Each story adds value independently and is testable before starting the next

---

## Notes

- `[P]` = different files, no unresolved dependencies; safe to parallelize
- All model `compute()` functions have the same signature — implement them in any order
- `main.py` is updated incrementally across US1–US3; ensure each update is backward-compatible
- `shared/` modules must exist before any service module is written (Phase 2 blocks Phase 3+)
- Dashboard (US4) reads pre-computed parquets — it does not re-run models at request time
