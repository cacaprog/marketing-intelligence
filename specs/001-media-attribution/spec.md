# Feature Specification: Media Attribution Model

**Feature Branch**: `001-media-attribution`

**Created**: 2026-05-20

**Status**: Draft

**Input**: User description: "let's create our first MVP: media attribution model."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Compare Attribution Models (Priority: P1)

A marketing analyst loads the attribution dashboard and sees revenue credited to each
channel under six different models side-by-side (last-touch, first-touch, linear,
time-decay, position-based, engagement-weighted). They can immediately identify which
channels win or lose depending on the model chosen.

**Why this priority**: This is the core deliverable. Without model comparison there is no
MVP — every other story builds on this output.

**Independent Test**: Can be fully tested by running the attribution service against the
dataset and verifying that six model result tables are produced with revenue sums equal
to total Closed Won ACV across all models.

**Acceptance Scenarios**:

1. **Given** the dataset is loaded, **When** the analyst runs the attribution service,
   **Then** each of the six models produces a channel × revenue table where the total
   revenue across channels equals total Closed Won ACV (within rounding tolerance).
2. **Given** the six model outputs, **When** the analyst views the comparison,
   **Then** they can see which channels are over-credited or under-credited relative
   to the other models.

---

### User Story 2 - Ground Truth Benchmark (Priority: P2)

The analyst can see how closely each heuristic model matches the causal ground truth
(`true_marginal_contribution`). A comparison table shows MAE and Pearson correlation
for each model vs. ground truth, ranked from best to worst.

**Why this priority**: This is what makes the dataset unique — the ability to objectively
rank attribution models. Without it the service is just an attribution calculator, not
an analytical tool.

**Independent Test**: Can be fully tested by verifying the benchmark table is produced
with six rows (one per model), each containing MAE and correlation values, and that the
ranking is consistent with the numeric values shown.

**Acceptance Scenarios**:

1. **Given** model outputs and ground truth values, **When** the benchmark runs,
   **Then** a table with columns [model, MAE, pearson_r, rank] is produced with exactly
   six rows.
2. **Given** the benchmark table, **When** the analyst inspects it,
   **Then** the model with the lowest MAE is ranked #1 and the ranking is monotonic.

---

### User Story 3 - ROAS by Channel (Priority: P3)

The analyst can calculate ROAS (Return on Ad Spend) per channel by joining attributed
revenue from any selected model against weekly channel spend. The output includes ROAS,
total spend, and attributed revenue for each paid channel.

**Why this priority**: ROAS is the primary business KPI for media investment decisions.
It ties the attribution output to actual budget data and makes the analysis actionable.

**Independent Test**: Can be fully tested by verifying that ROAS values are only present
for paid channels (paid_search, linkedin_ads, meta_ads, email_marketing, webinar_evento)
and that ROAS = attributed_revenue / spend_brl for each row.

**Acceptance Scenarios**:

1. **Given** a selected attribution model and the channel spend table, **When** the ROAS
   calculator runs, **Then** output contains one row per paid channel with
   `roas = attributed_revenue / spend_brl`.
2. **Given** the ROAS output, **When** the analyst reviews it,
   **Then** organic_search and direct channels are excluded (zero spend, ROAS undefined).

---

### User Story 4 - Interactive Dashboard (Priority: P4)

The analyst can explore all of the above through a web dashboard: select which
attribution model to view, see the channel ranking bar chart update, inspect the ground
truth benchmark table, and view ROAS figures — all without writing code.

**Why this priority**: The dashboard makes the service accessible to non-technical
stakeholders and is the primary demo surface for the MVP.

**Independent Test**: Can be fully tested by launching the dashboard, selecting each of
the six models from a dropdown, and verifying the channel chart and ROAS table update
accordingly.

**Acceptance Scenarios**:

1. **Given** the dashboard is running, **When** the analyst selects a model from the
   dropdown, **Then** the channel attribution chart and ROAS table update to reflect
   that model's output within 2 seconds.
2. **Given** the dashboard, **When** the analyst views the benchmark section,
   **Then** all six models are listed with their MAE and correlation values visible
   without scrolling on a standard laptop screen.

---

### Edge Cases

- What happens when an opportunity has only one touchpoint? (All credit goes to that
  single touch for all multi-touch models — should produce the same result as last-touch.)
- How does the system handle opportunities with `is_won = 0`? (Only Closed Won
  opportunities contribute revenue to any model.)
- What happens when `channel_spend` has gaps for a given week? (ROAS is calculated on
  total spend across the full dataset period, not per-week.)
- How are `Em Andamento` (in-progress) opportunities treated? (Excluded from all
  revenue calculations — only Closed Won is counted.)

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The service MUST implement all six attribution models: last-touch,
  first-touch, linear, time-decay (configurable half-life, default 14 days),
  position-based (40/20/40), and engagement-weighted.
- **FR-002**: The service MUST restrict revenue attribution to `is_won = 1`
  opportunities only.
- **FR-003**: The service MUST produce a ground truth benchmark table comparing each
  model's channel-level attribution against `true_marginal_contribution`, reporting
  MAE and Pearson correlation.
- **FR-004**: The service MUST calculate ROAS for all paid channels by joining
  attributed revenue with `channel_spend`, excluding channels with zero spend.
- **FR-005**: The service MUST expose a web dashboard that allows model selection and
  renders updated charts and tables interactively.
- **FR-006**: All model outputs MUST be reproducible — running the service twice on the
  same dataset MUST produce identical results.

### Key Entities *(include if feature involves data)*

- **AttributionResult**: Channel-level revenue table output by a single model;
  attributes: model_name, channel, attributed_revenue_brl, attributed_opps, share_pct.
- **BenchmarkResult**: Per-model accuracy row; attributes: model_name, mae,
  pearson_r, rank.
- **RoasResult**: Per-channel ROAS row; attributes: channel, model_name,
  attributed_revenue_brl, total_spend_brl, roas, cpql (cost per qualified lead),
  cpo (cost per opportunity).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All six attribution models complete and produce output for the full
  18-month dataset in under 30 seconds on a standard laptop.
- **SC-002**: Revenue totals across channels are consistent across models — total
  attributed revenue equals total Closed Won ACV for every model (tolerance: ±1 BRL
  due to floating point rounding).
- **SC-003**: The ground truth benchmark identifies the best-performing heuristic model
  (lowest MAE vs. `true_marginal_contribution`) among the six.
- **SC-004**: ROAS values are available for all five paid channels (paid_search,
  linkedin_ads, meta_ads, email_marketing, webinar_evento).
- **SC-005**: A non-technical stakeholder can switch between all six models in the
  dashboard and read channel rankings without any instructions.

## Assumptions

- The dataset at `data/raw/b2b_attribution.db` is already generated and available
  (via `generate_dataset.py`).
- Attribution is calculated at the channel level (not campaign or ad level) for this MVP.
- Time-decay half-life defaults to 14 days, matching the generative model's decay
  parameter — this can be changed via a config constant.
- ROAS is calculated over the full dataset period (2023-01-01 to 2024-06-30), not
  rolling weekly.
- The dashboard is for local/demo use only — no authentication or multi-user support
  is required for this MVP.
- Cross-channel journeys (touchpoints from a secondary channel within the same
  opportunity) are attributed to the channel recorded on each touchpoint row, not
  the opportunity's `first_touch_channel`.
