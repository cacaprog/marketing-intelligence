# Research: Media Attribution Model

**Phase 0 output for plan.md**
**Date**: 2026-05-20

---

## Decision 1: Dashboard Framework

**Decision**: Streamlit

**Rationale**: Streamlit requires the least boilerplate for a single-analyst local dashboard.
A dropdown + chart + table layout maps to ~50 lines of Streamlit code vs. significantly
more with Dash. No multi-user, no routing, no callbacks — Streamlit's reactive model fits
perfectly.

**Alternatives considered**:
- Dash: More flexible but requires callback decorators and layout objects; overkill for a
  single-page local demo.
- Jupyter: Not a shareable web app; poor for interactive model switching.

---

## Decision 2: Attribution Model Implementation

**Decision**: Pure pandas operations — no external attribution library.

**Rationale**: All six models are straightforward grouped aggregations on the
`touchpoints` table. Keeping the logic in plain pandas makes each model transparent,
independently testable, and free of hidden dependencies. The dataset is small enough
(~6K touchpoints) that vectorized pandas is fast.

**Alternatives considered**:
- `attr` / `shapley-attribution` libraries: Add dependency weight without simplifying
  the math; also harder to benchmark against a custom ground truth.
- SQL-based computation in SQLite: Possible but mixes presentation and logic awkwardly;
  Python is cleaner for the normalization step.

---

## Decision 3: Time-Decay Half-Life

**Decision**: 14 days default, configurable constant in `shared/config.py`.

**Rationale**: 14 days is the half-life used in `generate_dataset.py` for the ground
truth weights (`decay = exp(−days/14)`). Using the same value gives the time-decay model
its best theoretical chance of matching ground truth — and makes the comparison fair.

**Alternatives considered**:
- 7 days: Too aggressive for a B2B SaaS cycle averaging 50+ days.
- 30 days: Under-weights recent touchpoints vs. the generative model.

---

## Decision 4: ROAS Calculation Period

**Decision**: Full dataset window (2023-01-01 → 2024-06-30), not rolling weekly.

**Rationale**: The attribution models produce total revenue figures over the full period;
matching the spend aggregation to the same window avoids period-mismatch distortion.
Rolling ROAS (weekly) is useful for trend analysis but is a v2 feature.

**Alternatives considered**:
- Rolling 4-week ROAS: More actionable but requires time-windowing the attribution spine,
  which is a separate feature (cohort service, service #02).

---

## Decision 5: Benchmark Metrics

**Decision**: MAE (Mean Absolute Error) + Pearson correlation at the channel level.

**Rationale**: Both metrics are interpretable without statistics background. MAE answers
"by how many BRL is this model off per channel on average?" — directly actionable.
Pearson answers "does this model rank channels in the right order?" — important for
budget reallocation decisions.

**Alternatives considered**:
- MAPE (Mean Absolute Percentage Error): Unstable when ground truth values are near zero
  (can happen for niche channels).
- RMSE: Penalizes large errors more but is harder to explain to non-technical analysts.
- Spearman rank correlation: Useful complement but duplicates information already conveyed
  by the channel ranking tables.

---

## Decision 6: Engagement-Weighted Model Weight Function

**Decision**: `weight = engagement_score / sum(engagement_score)` per opportunity.

**Rationale**: Linear normalization is the simplest interpretation of "credit
proportional to engagement." The `engagement_score` column (1–100) already encodes
touch type importance (sales_call=90, impression=10), so no additional calibration
is needed.

**Alternatives considered**:
- Softmax over engagement scores: Creates sharper distributions but loses the intuitive
  proportionality.
- Engagement score squared: Amplifies high-engagement touches further; introduces a
  parameter that is hard to justify to stakeholders.

---

## All NEEDS CLARIFICATION Resolved

No `[NEEDS CLARIFICATION]` markers were present in the spec. All decisions above were
derived from dataset documentation, CLAUDE.md, and constitution principles.
