import math

import numpy as np

from src.consensus.reputation import ReputationEngine
from src.network.node import VirtualNode


def create_partial_mesh(
    node_ids: list[str],
    positions: list[tuple],
    rng: np.random.Generator | None = None,
) -> tuple[list[VirtualNode], ReputationEngine, dict]:
    """
    Create N nodes where each node connects to floor(sqrt(N)) nearest neighbours.
    Returns (nodes, reputation, positions_dict).
    positions_dict maps node_id -> (x_m, y_m).
    """
    rng        = rng if rng is not None else np.random.default_rng(0)
    reputation = ReputationEngine()
    nodes      = [VirtualNode(nid, reputation) for nid in node_ids]
    n          = len(nodes)
    k          = max(1, math.floor(math.sqrt(n)))

    genesis = nodes[0].init_genesis()
    for node in nodes[1:]:
        node.receive_genesis(genesis)

    # register all public keys on every chain (shared PKI)
    for i, node in enumerate(nodes):
        for j, other in enumerate(nodes):
            if i != j:
                node.chain.register_public_key(other.node_id, other.public_key_pem)

    pos_arr = np.array(positions, dtype=float)

    for i, node in enumerate(nodes):
        dists   = np.linalg.norm(pos_arr - pos_arr[i], axis=1)
        dists[i] = np.inf
        nearest = np.argsort(dists)[:k]
        for j in nearest:
            node.register_peer(nodes[j])

    positions_dict = {nid: positions[i] for i, nid in enumerate(node_ids)}
    return nodes, reputation, positions_dict


def create_full_mesh(node_ids: list[str]) -> tuple[list[VirtualNode], ReputationEngine]:
    """
    Create N nodes sharing a single ReputationEngine.
    All nodes are fully connected. Node 0 creates the genesis block.
    Returns (nodes, reputation).
    """
    reputation = ReputationEngine()
    nodes = [VirtualNode(nid, reputation) for nid in node_ids]

    genesis = nodes[0].init_genesis()
    for node in nodes[1:]:
        node.receive_genesis(genesis)

    for i, node in enumerate(nodes):
        for j, peer in enumerate(nodes):
            if i != j:
                node.register_peer(peer)

    return nodes, reputation
