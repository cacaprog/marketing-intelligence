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
class RoasResult:
    model_name: str
    channel: str
    attributed_revenue_brl: float
    total_spend_brl: float
    roas: float
    cpql: float
    cpo: float
