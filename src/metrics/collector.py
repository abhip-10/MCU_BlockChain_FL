"""MetricsCollector: accumulate per-round results and export to CSV."""
from dataclasses import dataclass, field
import pandas as pd


@dataclass
class RoundMetrics:
    scenario:               str
    n_nodes:                int
    n_byzantine:            int
    n_failures:             int
    consensus_latency_ms:   float
    block_delivery_rate:    float
    byzantine_rejection_rate: float
    fl_weight_delta:        float = 0.0
    fl_convergence_round:   int   = -1
    chain_consistent:       bool  = True
    sync_time_s:            float = 0.0
    global_comms:           int   = 0


class MetricsCollector:
    def __init__(self) -> None:
        self._rows: list[RoundMetrics] = []

    def record(self, m: RoundMetrics) -> None:
        self._rows.append(m)

    def to_dataframe(self) -> pd.DataFrame:
        return pd.DataFrame([vars(r) for r in self._rows])

    def export_csv(self, path: str) -> None:
        self.to_dataframe().to_csv(path, index=False)
        print(f"  Metrics written -> {path}")
