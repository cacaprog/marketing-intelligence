from dataclasses import dataclass


@dataclass
class AttributionResult:
    model_name: str
    channel: str
    attributed_revenue_brl: float
    attributed_opps: int
    share_pct: float


@dataclass
class BenchmarkResult:
    model_name: str
    mae: float
    pearson_r: float
    rank: int


@dataclass
class AllocationRecommendation:
    channel: str
    current_spend_brl: float
    channel_efficiency: float
    recommended_spend_brl: float
    expected_revenue_brl: float
    expected_roas: float | None
    budget_input_brl: float
    subpopulation_caveat: bool = True


@dataclass
class RoasResult:
    model_name: str
    channel: str
    attributed_revenue_brl: float
    total_spend_brl: float
    roas: float
    cpql: float
    cpo: float
