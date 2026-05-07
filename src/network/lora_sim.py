"""
LoRa PHY simulation: log-distance path-loss model for indoor first-responder mesh.
Parameters calibrated to dense urban / building-penetration (NLOS) scenario,
matching measured LoRa SX1276 data from Aref & Stirling-Gallacher (2014).

PL(d) = 55 + 10*3.5*log10(d) + X_sigma    X_sigma ~ N(0, 8) dB
RSSI   = 14 - PL(d)                         [dBm]
PDR    = sigmoid((RSSI - (-131)) / 8)

Shadow fading:
  Default — independent per-link N(0, 8dB): fast to compute, sufficient for
  protocol correctness tests (M1-M5 baseline).

  Gudmundson (1991) spatially correlated field — optional ShadowField object
  passed to LoRaChannel at construction. Nearby links share correlated fading,
  producing realistic dead-zone clustering (whole building sector going dark).
  Use for M5 delivery-rate and partition studies.
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


class ShadowField:
    """
    Spatially correlated log-normal shadow fading field (Gudmundson 1991).

    Precomputed on a grid at mesh-build time. Shadow values at nearby
    locations are correlated with decorrelation distance d_corr (~10 m
    indoors). For a link between src and dst the shadow fading is the
    average of the field values at both endpoints — standard approximation
    for the Gudmundson model.

    Parameters
    ----------
    area_m    : simulation area side length in metres
    grid_res  : grid spacing in metres (10 m default — coarse enough to
                be fast, fine enough to capture building-scale clustering)
    sigma_db  : shadow fading standard deviation (dB)
    d_corr_m  : spatial decorrelation distance (m) — ~10 m for dense indoor
    rng       : numpy random Generator for reproducibility
    """

    def __init__(self, area_m: float = 200.0, grid_res: float = 10.0,
                 sigma_db: float = SHADOW_STD, d_corr_m: float = 10.0,
                 rng: np.random.Generator | None = None) -> None:
        from scipy.spatial.distance import cdist

        rng  = rng or np.random.default_rng(0)
        n    = int(area_m / grid_res) + 1
        xs   = np.linspace(0.0, area_m, n)
        ys   = np.linspace(0.0, area_m, n)
        xx, yy = np.meshgrid(xs, ys)
        pts  = np.column_stack([xx.ravel(), yy.ravel()])  # (n*n, 2)

        # Exponential covariance kernel: C(d) = sigma^2 * exp(-d / d_corr)
        D    = cdist(pts, pts)
        cov  = (sigma_db ** 2) * np.exp(-D / d_corr_m)
        vals = rng.multivariate_normal(np.zeros(len(pts)), cov)

        self._field = vals.reshape(n, n)   # (n_y, n_x)
        self._xs    = xs
        self._ys    = ys

    def get(self, pos: tuple) -> float:
        """Shadow fading (dB) at position (x, y) via nearest-grid lookup."""
        xi = int(np.searchsorted(self._xs, pos[0], side="right")) - 1
        yi = int(np.searchsorted(self._ys, pos[1], side="right")) - 1
        xi = max(0, min(xi, len(self._xs) - 1))
        yi = max(0, min(yi, len(self._ys) - 1))
        return float(self._field[yi, xi])


class LoRaChannel:
    """
    LoRa radio channel model.

    Parameters
    ----------
    rng          : numpy random Generator (used for independent shadowing
                   fallback and stochastic delivery decision)
    shadow_field : optional ShadowField for Gudmundson correlated fading.
                   When None, per-link independent N(0, SHADOW_STD) is used.
    """

    def __init__(self, rng: np.random.Generator | None = None,
                 shadow_field: ShadowField | None = None) -> None:
        self._rng    = rng if rng is not None else np.random.default_rng(0)
        self._shadow = shadow_field

    def pdr(self, d_m: float) -> float:
        return pdr_deterministic(d_m)

    def deliver(self, src_pos: tuple, dst_pos: tuple) -> bool:
        d = math.dist(src_pos, dst_pos)

        if self._shadow is not None:
            # Gudmundson: link shadow = mean of endpoint shadow values
            shadow = (self._shadow.get(src_pos) + self._shadow.get(dst_pos)) / 2.0
        else:
            shadow = float(self._rng.normal(0.0, SHADOW_STD))

        pl   = PL0 + 10.0 * PATH_LOSS_EXP * math.log10(max(d, 1.0)) + shadow
        rssi = PTX_DBM - pl
        p    = _sigmoid((rssi - SENSITIVITY) / PDR_SCALE)
        return bool(self._rng.random() < p)
