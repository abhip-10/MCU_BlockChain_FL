"""
LoRa PHY simulation: log-distance path-loss model for indoor first-responder mesh.
Parameters calibrated to dense urban / building-penetration (NLOS) scenario,
matching measured LoRa SX1276 data from Aref & Stirling-Gallacher (2014).

PL(d) = 55 + 10*3.5*log10(d) + X_sigma    X_sigma ~ N(0, 8) dB
RSSI   = 14 - PL(d)                         [dBm]
PDR    = sigmoid((RSSI - (-131)) / 8)
"""
import math

import numpy as np

PTX_DBM       = 14.0
SENSITIVITY   = -131.0   # SX1276 SF10 BW125 receiver sensitivity
PATH_LOSS_EXP = 3.5      # dense urban / NLOS (2.7 is outdoor LOS)
SHADOW_STD    = 8.0      # dB -- higher indoors
PL0           = 55.0     # dB at 1 m -- measured indoors
PDR_SCALE     = 8.0      # sigmoid steepness for NLOS link uncertainty


def _sigmoid(x: float) -> float:
    return 1.0 / (1.0 + math.exp(-max(-500.0, min(500.0, x))))


def pdr_deterministic(d_m: float) -> float:
    """PDR with no shadow fading (used for table and plot generation)."""
    d_m = max(d_m, 1.0)
    pl   = PL0 + 10.0 * PATH_LOSS_EXP * math.log10(d_m)
    rssi = PTX_DBM - pl
    return _sigmoid((rssi - SENSITIVITY) / PDR_SCALE)


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
        p      = _sigmoid((rssi - SENSITIVITY) / PDR_SCALE)
        return bool(self._rng.random() < p)
