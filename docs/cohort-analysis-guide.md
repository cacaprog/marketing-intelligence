# How to Read the Cohort Analysis

**Date**: 2026-05-20
**Service**: `services/02-cohort/`

---

## The Core Question

Cohort analysis answers one fundamental question: **"Is the quality of our lead acquisition improving or degrading over time?"**

---

## The Cohort Revenue Heatmap

Each row is a month you acquired leads. Each column is how much time has passed. The cell value is cumulative closed-won revenue.

```
             1m      3m      6m      9m      12m
2023-01   50,000  180,000  420,000  610,000  780,000
2023-02   30,000  110,000  280,000  390,000  510,000
2023-03   80,000  220,000  500,000  720,000  900,000
...
2024-05   15,000   45,000   (grey)   (grey)   (grey)
```

**Grey cells** = not enough time has passed to observe that window. This is the "not yet observable" distinction — if you showed zero there, you'd think recent campaigns are underperforming when they're actually just young.

**What you're looking for**: do earlier columns (3m, 6m) for recent cohorts approach the same values as earlier cohorts at the same columns? If 2024-Q1 cohorts are hitting the same 6-month revenue as 2023-Q1 cohorts, acquisition quality is stable. If they're lower, something degraded.

---

## The Funnel Table

```
cohort_month  leads  mqls  opps  won  mql_rate  win_rate
2023-01        420   180    95   42    42.9%     10.0%
2023-06        390   120    60   22    30.8%      5.6%
2024-01        350   160    80   30    45.7%      8.6%
```

**What this tells you**: *where* a cohort is leaking. Revenue can be low for two completely different reasons:

- Low `mql_rate` → **lead quality problem** — you're acquiring leads that never qualify. Might mean wrong targeting, wrong channels, or inflated volume from low-intent sources.
- Low `opp_to_win_rate` → **sales problem** — leads qualify fine but sales can't close them. Cohort analysis surfaces this because it's segmented by acquisition month, not close month.
- Both rates normal but low revenue → **deal size problem** — right people, right conversion, but smaller contracts.

---

## The Channel Segmentation

This is where actionable decisions live. Example reading:

```
cohort 2023-Q2:
  LinkedIn    mql_rate=52%  win_rate=14%  6m_revenue=320,000
  Paid Search mql_rate=28%  win_rate= 6%  6m_revenue=180,000
  Organic     mql_rate=38%  win_rate=11%  6m_revenue=140,000
```

**What this tells you**: LinkedIn cohorts from Q2 2023 were worth 78% more at 6 months than paid search cohorts, and they converted at twice the rate. That's not visible in any single-period report — it only emerges when you track the same acquisition cohort forward in time.

---

## The Decisions a Company Can Take

**1. Budget reallocation** — if LinkedIn cohorts consistently show higher 6-month and 12-month revenue across multiple acquisition months, that's the evidence to shift spend. The key word is *consistently*: one good month might be noise; three consecutive cohorts with higher revenue is signal.

**2. Identifying deteriorating channels** — if Paid Search cohorts from 2023-H1 had good 12-month revenue but 2023-H2 cohorts are tracking lower at 6 months, something changed mid-year (bid competition, audience saturation, creative fatigue). You can investigate *before* the 12-month number confirms it.

**3. Sales cycle benchmarking** — the shape of the revenue curve (how steeply it rises from 1m to 6m) tells you the typical sales cycle length per channel. LinkedIn might have a slower ramp (longer sales cycles) but higher 12-month terminal value. Paid Search might close faster but smaller. That changes how you plan cash flow and quota targets.

**4. Forecasting** — if you know that 2024-Q1 cohorts are tracking at 80% of 2023-Q1 cohorts at the 3-month mark, and 2023-Q1 eventually reached $780K by month 12, you can project 2024-Q1's likely 12-month value right now, without waiting.

**5. Flagging the low-sample warning** — the `low_sample_flag` (< 5 leads) matters because a channel with 2 leads and 1 win looks like a 50% win rate. Don't make budget decisions on flagged rows. They're useful for qualitative signals only.

---

## The Key Insight Over a Standard Dashboard

A standard marketing dashboard tells you "we closed $2M this month." That mixes cohorts from 8 different acquisition months all closing simultaneously. You can't tell if this month's closures are from a great January campaign or a mediocre March campaign that finally converted.

Cohort analysis separates those. It answers: **"How much is each generation of leads actually worth, and is each generation worth more or less than the previous one?"** That's the difference between reactive reporting and strategic acquisition management.
