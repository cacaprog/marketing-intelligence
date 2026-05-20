# Data-Driven Attribution Model: Rationale & How It Works

**Date**: 2026-05-20
**Service**: `services/01-attribution/`

---

## The core question

Both heuristics and the ML model answer the same question:

> "How much credit does each touchpoint deserve for the conversion?"

They differ fundamentally in *how* they answer it.

---

## Heuristics: single-rule approaches (no learning)

Each heuristic applies one fixed rule derived from touchpoint position or engagement.
No training. No data. Same rule for every journey.

| Model | Rule | Feature used |
|---|---|---|
| Last-touch | 100% credit to the final touchpoint | `is_last_touch` |
| First-touch | 100% credit to the entry point | `is_first_touch` |
| Time-decay | Exponential weight by recency | `days_before_opp_creation` |
| Linear | Equal weight to all touches | `total_touches_in_journey` |
| Position-based | 40% first + 40% last + 20% middle | position |
| Engagement-weighted | Weight proportional to interaction quality | `engagement_score` |

**The problem**: each model extrapolates one assumption uniformly to every journey,
regardless of context.

---

## LightGBM model: learns from data

Trained via supervised regression to predict `true_marginal_contribution` —
the causal ground truth from the SCM generative model.

### Features (per touchpoint row)

| Feature | What it captures |
|---|---|
| `channel` | Which channel this touch came from (7 categories) |
| `touch_type` | click, demo_request, sales_call, form_fill, etc. (6 categories) |
| `engagement_score` | Quality / depth of the interaction (1–100) |
| `touch_sequence` | Position in the journey (1 = first touch) |
| `total_touches_in_journey` | Total length of the customer journey |
| `days_before_opp_creation` | How far before conversion this touch happened |
| `is_first_touch` | Entry point flag (0/1) |
| `is_last_touch` | Final touch flag (0/1) |

### Training setup

- **Algorithm**: LightGBM regression (objective = MAE)
- **Target**: `true_marginal_contribution` (float, sums to 1.0 per opportunity)
- **Temporal split**: train on `opp.created_date < 2024-03-01`, test on `≥ 2024-03-01`
- **Post-processing**: clip predictions to ≥ 0, then normalize per opportunity so weights sum to 1.0

---

## Why the ML model outperforms heuristics

Instead of applying one rule uniformly, the model learns **interactions** between features.

**Example — same touch type, different context:**

| Journey context | Rule-based (last-touch) | ML model |
|---|---|---|
| `demo_request` + `is_last_touch`, 2-touch journey | 100% | ~70% |
| `demo_request` + `is_last_touch`, 10-touch journey | 100% | ~40% |
| `click` + `is_last_touch`, same channel | 100% | ~25% |

The last-touch heuristic gives 100% in all three cases.
The ML model recognises that the same touch *type* is less decisive when it's the last
of many touches, and less decisive when it was a passive click vs. an active demo request.

This nuanced, context-sensitive weighting is what produces lower MAE on held-out data.

---

## What the model found in this dataset

**Top feature: `is_last_touch` — 59.6% gain importance.**

This tells us the synthetic SCM generative model puts significant weight on late-stage
touches when allocating causal contributions. The LightGBM model *discovered* this from
data rather than having it hard-coded — unlike the last-touch heuristic, it still adjusts
the weight based on journey length, touch type, and engagement.

### Full feature importance ranking

| Rank | Feature | Importance (gain, normalized) |
|---|---|---|
| 1 | `is_last_touch` | 0.596 |
| 2–8 | (other features) | remaining 0.404 |

---

## Benchmark result (held-out test set: 2024-03-01 → 2024-06-30)

All models evaluated on the same held-out period. MAE measured against
`true_marginal_contribution` at channel-level revenue share.

| Rank | Model | MAE | Pearson r |
|---|---|---|---|
| 1 | **data_driven** | **0.014** | 1.000 |
| 2 | last_touch | 0.022 | 1.000 |
| 3 | engagement_weighted | 0.184 | 0.999 |
| 4 | time_decay | 0.222 | 1.000 |
| 5 | linear | 0.787 | 0.993 |
| 6 | position_based | 1.972 | 0.963 |
| 7 | first_touch | 4.954 | 0.852 |

---

## Key takeaway

Heuristics encode human assumptions about what makes a touchpoint valuable.
The ML model lets the data decide — and because the training target is the actual
causal contribution from the generative model, the model converges on something
closer to ground truth than any single rule can.

**The limitation**: `is_last_touch` dominating feature importance means the model
is behaving similarly to last-touch, but with contextual adjustments. On a real
dataset without causal ground truth, the training target would need to be a conversion
outcome (won/lost), which is a weaker signal and would require more data and careful
design to avoid leakage.
