"""
Hierarchical / clustered FedAvg.
Two-tier aggregation:
  1. k = floor(sqrt(N)) clusters formed by k-means on node positions.
  2. Intra-cluster FedAvg (with DP noise) at each cluster head.
  3. Global FedAvg across cluster heads -> global model pushed to all nodes.
Communication cost: O(sqrt(N)) global exchanges vs O(N) for flat FedAvg.
"""
import math

import numpy as np

from src.federated.fedavg import fedavg
from src.federated.dp_noise import add_gaussian_noise


def _kmeans(positions: list, k: int, iters: int = 20, rng=None) -> list:
    """Simple k-means. Returns cluster label per node (list of ints)."""
    rng    = rng or np.random.default_rng(1)
    pts    = np.array(positions, dtype=float)
    n      = len(pts)
    idx    = rng.choice(n, k, replace=False)
    cents  = pts[idx].copy()

    labels = np.zeros(n, dtype=int)
    for _ in range(iters):
        dists  = np.linalg.norm(pts[:, None] - cents[None, :], axis=2)
        labels = np.argmin(dists, axis=1)
        for c in range(k):
            members = pts[labels == c]
            if len(members):
                cents[c] = members.mean(axis=0)

    return labels.tolist()


def hierarchical_fedavg(
    weights_list: list,       # one np.ndarray per node
    positions: list,          # one (x, y) per node (same order)
    epsilon: float = 10.0,
    delta: float   = 1e-5,
    C: float       = 1.0,
) -> list:
    """
    Run two-tier FedAvg. Returns updated weight list (one per node).
    Also returns (n_global_comms, n_local_comms) as a tuple via second return value.
    """
    n = len(weights_list)
    k = max(2, math.floor(math.sqrt(n)))

    labels        = _kmeans(positions, k)
    cluster_models = []
    local_comms    = 0

    for c in range(k):
        members = [weights_list[i] for i, lbl in enumerate(labels) if lbl == c]
        if not members:
            continue
        noisy   = [add_gaussian_noise(w, epsilon, delta, C) for w in members]
        cluster_models.append(fedavg(noisy))
        local_comms += len(members)

    global_model = fedavg(cluster_models)
    n_global_comms = len(cluster_models)

    updated = [global_model.copy() for _ in weights_list]
    return updated, (n_global_comms, local_comms)
