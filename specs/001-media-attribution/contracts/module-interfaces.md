# Module Interfaces: Media Attribution Service

**Type**: Internal Python module contracts
**Date**: 2026-05-20

Each model module MUST expose a single public function matching this signature.
All other helpers are private (`_` prefix).

---

## Model Module Contract

Every file in `services/01-attribution/models/` MUST export exactly one public function:

```python
def compute(spine: pd.DataFrame) -> pd.DataFrame:
    """
    Args:
        spine: AttributionSpine DataFrame (see data-model.md).
              Must contain columns: opp_id, touchpoint_id, channel,
              amount_brl, touch_sequence, total_touches, days_before_opp_creation,
              engagement_score, is_first_touch, is_last_touch.

    Returns:
        spine with one additional column:
          weight (float): fractional credit for this touchpoint, 0.0–1.0.
          Invariant: weight.groupby('opp_id').sum() == 1.0 for all opps.
    """
```

---

## Analysis Module Contracts

### `analysis/compare_models.py`

```python
def run_all_models(spine: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """
    Runs all six model compute() functions and returns a dict keyed by model name.
    Each value is the spine DataFrame with the weight column added.

    Keys: "last_touch", "first_touch", "linear", "time_decay",
          "position_based", "engagement_weighted"
    """

def to_channel_table(weighted_spine: pd.DataFrame, model_name: str) -> list[AttributionResult]:
    """
    Aggregates a weighted spine to channel-level AttributionResult objects.
    """
```

### `analysis/roas_calculator.py`

```python
def compute_roas(
    attribution_results: list[AttributionResult],
    spend_df: pd.DataFrame,
    leads_df: pd.DataFrame,
    opps_df: pd.DataFrame,
) -> list[RoasResult]:
    """
    Joins attribution results with spend data.
    Excludes channels where total_spend_brl == 0.
    """
```

### `analysis/benchmark.py` (ground truth comparison)

```python
def benchmark_models(
    model_results: dict[str, list[AttributionResult]],
    ground_truth: list[AttributionResult],
) -> list[BenchmarkResult]:
    """
    Computes MAE and Pearson correlation for each model vs. ground truth.
    Returns list sorted by MAE ascending (rank 1 = best).
    ground_truth is the AttributionResult list from true_marginal_contribution.
    """
```

---

## Dashboard Contract (`dashboard/app.py`)

**Entry point**: `streamlit run services/01-attribution/dashboard/app.py`

**Expected inputs** (loaded at startup, not passed as args):
- `data/processed/01-attribution/attribution_results.parquet`
- `data/processed/01-attribution/benchmark_results.parquet`
- `data/processed/01-attribution/roas_results.parquet`

**UI contract**:
- Model selector: `st.selectbox` with all six model names
- Attribution chart: horizontal bar chart of channel vs. attributed_revenue_brl
- Benchmark table: sorted by rank ascending, columns [model, mae, pearson_r, rank]
- ROAS table: for selected model only, columns [channel, roas, spend_brl, attributed_revenue_brl]

---

## CLI Contract (`main.py`)

```
python services/01-attribution/main.py [--output-dir PATH]
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output-dir` | `data/processed/01-attribution/` | Where to write parquet/CSV outputs |

**Exit codes**:
- `0`: Success, all outputs written
- `1`: Dataset not found or validation failure
