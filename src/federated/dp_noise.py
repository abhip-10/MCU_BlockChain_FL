"""
Differential Privacy for Federated Learning.
Implements the Gaussian mechanism for (epsilon, delta)-DP weight broadcasts.

Privacy guarantee: with epsilon=1.0, delta=1e-5, an observer who intercepts
the broadcast cannot reconstruct the raw local weights to within L2 norm C.
"""
from math import log, sqrt

import numpy as np


def clip_update(delta: np.ndarray, C: float = 1.0) -> np.ndarray:
    """L2-norm clipping: scale delta down if ||delta|| > C."""
    norm = np.linalg.norm(delta)
    return delta * (C / norm) if norm > C else delta


def add_gaussian_noise(weights: np.ndarray,
                       epsilon: float = 1.0,
                       delta: float = 1e-5,
                       C: float = 1.0) -> np.ndarray:
    """
    Gaussian mechanism: add calibrated noise for (epsilon, delta)-DP.
    sigma = C * sqrt(2 * ln(1.25 / delta)) / epsilon
    """
    sigma = C * sqrt(2.0 * log(1.25 / delta)) / epsilon
    noise = np.random.normal(0.0, sigma, weights.shape)
    return weights + noise


def dp_sigma(epsilon: float = 1.0, delta: float = 1e-5, C: float = 1.0) -> float:
    """Return the noise standard deviation for the given DP parameters."""
    return C * sqrt(2.0 * log(1.25 / delta)) / epsilon
