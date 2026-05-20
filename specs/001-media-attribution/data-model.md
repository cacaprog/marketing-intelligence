# Data Model: Media Attribution Model

**Phase 1 output for plan.md**
**Date**: 2026-05-20

---

## Input Tables (read-only from `data/raw/b2b_attribution.db`)

### touchpoints

Primary spine for all attribution computation.

| Column | Type | Role |
|--------|------|------|
| touchpoint_id | str | PK |
| opp_id | str | FK → opportunities; groups touchpoints per deal |
| lead_id | str | FK → leads |
| touch_sequence | int | Position (1 = first) |
| total_touches_in_journey | int | Total touches for this opp |
| channel | str | Attribution dimension |
| touch_type | str | Qualitative type (used in engagement-weighted model) |
| engagement_score | int | 1–100; used in engagement-weighted model |
| days_before_opp_creation | int | Used in time-decay model |
| is_first_touch | int | 0/1 flag |
| is_last_touch | int | 0/1 flag |
| true_marginal_contribution | float | Ground truth (sums to 1.0 per opp) |
| attributed_revenue_brl | float | Revenue pre-attributed by ground truth |

### opportunities (filter: `is_won = 1`)

| Column | Type | Role |
|--------|------|------|
| opp_id | str | PK |
| amount_brl | float | ACV used as revenue basis |
| is_won | int | Filter: only 1 values contribute revenue |

### channel_spend (for ROAS)

| Column | Type | Role |
|--------|------|------|
| channel | str | Join key |
| spend_brl | float | Aggregated over full period |

---

## Output Schemas

### AttributionResult

One row per channel per model. Written to `data/processed/01-attribution/`.

```python
@dataclass
class AttributionResult:
    model_name: str         # "last_touch" | "first_touch" | "linear" |
                            #  "time_decay" | "position_based" | "engagement_weighted"
    channel: str            # e.g., "linkedin_ads"
    attributed_revenue_brl: float
    attributed_opps: int    # distinct opp count with ≥1 touch on this channel
    share_pct: float        # attributed_revenue / total_revenue * 100
```

File: `data/processed/01-attribution/attribution_results.parquet`
(also exported as CSV: `attribution_results.csv`)

---

### BenchmarkResult

One row per model. Written alongside attribution results.

```python
@dataclass
class BenchmarkResult:
    model_name: str
    mae: float              # mean(|model_channel_share - truth_channel_share|)
    pearson_r: float        # correlation of channel-level shares vs. truth
    rank: int               # 1 = best (lowest MAE)
```

File: `data/processed/01-attribution/benchmark_results.parquet`

---

### RoasResult

One row per paid channel × model combination.

```python
@dataclass
class RoasResult:
    model_name: str
    channel: str
    attributed_revenue_brl: float
    total_spend_brl: float
    roas: float             # attributed_revenue / spend_brl
    cpql: float             # spend / qualified_leads (from leads table)
    cpo: float              # spend / won_opps
```

File: `data/processed/01-attribution/roas_results.parquet`

---

## Intermediate Computation Objects

### AttributionSpine (internal, not persisted)

Pandas DataFrame built once, shared by all model functions.

| Column | Notes |
|--------|-------|
| opp_id | |
| touchpoint_id | |
| channel | |
| amount_brl | Joined from opportunities |
| touch_sequence | |
| total_touches | |
| days_before_opp_creation | |
| engagement_score | |
| is_first_touch | |
| is_last_touch | |
| true_marginal_contribution | Ground truth weight |

Built by `shared/db.py` helper; all six models receive this as input and return
a copy with an added `weight` column (float, sums to 1.0 per opp_id).

---

## State Transitions

None — this is a stateless batch computation. The service reads, computes, writes,
and exits. No mutable shared state between model runs.

---

## Validation Rules

- `weight` column per opp_id MUST sum to 1.0 (±1e-9 floating point tolerance)
- `attributed_revenue_brl` per opp MUST equal `amount_brl × weight` for every touchpoint
- Total attributed revenue across all channels MUST equal total Closed Won ACV
- `roas` is undefined (and excluded) for channels with `total_spend_brl == 0`
