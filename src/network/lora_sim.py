"""
LoRa PHY simulation: log-distance path-loss model (SX1276, SF10, BW125 kHz).
PL(d) = 40 + 10*2.7*log10(d) + X_sigma    X_sigma ~ N(0, 6) dB
RSSI   = 14 - PL(d)
PDR    = sigmoid((RSSI - (-131)) / 4)
"""
import math

import numpy as np

PTX_DBM       = 14.0
SENSITIVITY   = -131.0
PATH_LOSS_EXP = 2.7
SHADOW_STD    = 6.0
PL0           = 40.0    # path loss at 1 m reference


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, x))))


def pdr_deterministic(d_m: float) -> float:
    """PDR with no shadow fading (used for table generation)."""
    d_m = max(d_m, 1.0)
    pl   = PL0 + 10.0 * PATH_LOSS_EXP * math.log10(d_m)
    rssi = PTX_DBM - pl
    return _sigmoid((rssi - SENSITIVITY) / 4.0)


class LoRaChannel:
    def __init__(self, rng: np.random.Generator | None = None) -> None:
        self._rng = rng if rng is not None else np.random.default_rng(0)

    def pdr(self, d_m: float) -> float:
        return pdr_deterministic(d_m)

    def deliver(self, src_pos: tuple, dst_pos: tuple) -> bool:
        d      = math.dist(src_pos, dst_pos)
        shadow = float(self._rng.normal(0.0, SHADOW_STD))
        pl     = PL0 + 10.0 * PATH_LOSS_EXP * math.log10(max(d, 1.0)) + shadow
        rssi   = PTX_DBM - pl
        p      = _sigmoid((rssi - SENSITIVITY) / 4.0)
        return bool(self._rng.random() < p)
