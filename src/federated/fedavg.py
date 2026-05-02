import numpy as np


def fedavg(weights_list: list[np.ndarray]) -> np.ndarray:
    """Federated averaging: element-wise mean across all weight vectors."""
    return np.mean(weights_list, axis=0)
