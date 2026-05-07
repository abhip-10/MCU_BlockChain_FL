"""
Real-time Pygame visual simulation of the LoRa mesh.
Runs 5 scenarios from M5; press SPACE to advance, Q to quit.

Keys:
  SPACE  next scenario
  P      pause / resume
  F / S  faster / slower
  O      toggle key overlay
  Q      quit
"""
import hashlib
import sys
import threading
import time

import numpy as np

sys.path.insert(0, ".")

from sim.event_bus import EventBus
from sim.visual_hooks import (HookedReputationEngine, HookedPoACoordinator,
                               HookedGossipProtocol)
from sim.visualizer import Visualizer

from src.blockchain.crypto import generate_keypair
from src.byzantine.attacker import ByzantineNode
from src.federated.dp_noise import add_gaussian_noise
from src.federated.fedavg import fedavg
from src.federated.local_model import LocalModel
from src.network.lora_sim import LoRaChannel, pdr_deterministic
from src.network.mesh import create_partial_mesh
from src.network.node import VirtualNode


# ------------------------------------------------------------------ #
#  Mesh builder                                                        #
# ------------------------------------------------------------------ #

def random_positions(n: int, area: float = 200.0, seed: int = 42) -> list:
    rng = np.random.default_rng(seed)
    xs  = rng.uniform(0, area, n)
    ys  = rng.uniform(0, area, n)
    return [(float(xs[i]), float(ys[i])) for i in range(n)]


def build_mesh(n: int, bus: EventBus, seed: int = 42,
               n_byzantine: int = 0, area: float = 200.0):
    rng       = np.random.default_rng(seed)
    node_ids  = [f"N{i:02d}" for i in range(n)]
    positions = random_positions(n, area=area, seed=seed)
    lora      = LoRaChannel(rng=rng)

    nodes, reputation, pos_dict = create_partial_mesh(node_ids, positions, rng=rng)

    # Swap in hooked classes
    hooked_rep = HookedReputationEngine(bus)
    # copy existing scores across
    for nid in node_ids:
        hooked_rep._scores = {}   # start fresh; nodes already at default 0.5
    poa    = HookedPoACoordinator(bus, hooked_rep)
    gossip = HookedGossipProtocol(bus)

    for node in nodes:
        node.reputation = hooked_rep
        node._poa       = poa

    # Replace last n_byzantine nodes with ByzantineNode instances
    byz_nodes = []
    for bi in range(n_byzantine):
        idx = n - 1 - bi
        old = nodes[idx]
        byz = ByzantineNode(old.node_id, hooked_rep)
        byz.chain          = old.chain
        byz._frame_counter = old._frame_counter
        for peer in old.peers:
            byz.register_peer(peer)
        for other in nodes:
            if other is not old and old in other.peers:
                other.peers[other.peers.index(old)] = byz
        nodes[idx] = byz
        byz_nodes.append(byz)

    node_map = {node.node_id: node for node in nodes}

    # Compute edge PDRs for visualizer
    edge_pdr: dict = {}
    for node in nodes:
        for peer in node.peers:
            a, b = node.node_id, peer.node_id
            key  = (min(a, b), max(a, b))
            if key not in edge_pdr:
                d = np.linalg.norm(
                    np.array(pos_dict[a]) - np.array(pos_dict[b]))
                edge_pdr[key] = pdr_deterministic(d)

    init_scores = {nid: hooked_rep.score(nid) for nid in node_ids}
    return nodes, node_map, pos_dict, edge_pdr, hooked_rep, poa, gossip, lora, byz_nodes, init_scores


# ------------------------------------------------------------------ #
#  Shared helpers                                                      #
# ------------------------------------------------------------------ #

def _gossip_after_commit(proposer, node_map, pos_dict, gossip, lora):
    committed = proposer.chain.blocks[-1]
    gossip.broadcast(proposer.node_id, committed, node_map, pos_dict, lora)


def _propose(node, event_type, payload, anomaly=0.05):
    return node.propose(event_type, payload, anomaly_score=anomaly)


# ------------------------------------------------------------------ #
#  Scenarios                                                           #
# ------------------------------------------------------------------ #

def scenario_a(bus: EventBus, viz: Visualizer, done: threading.Event):
    """N=10, 1 Byzantine — PKI rejection of all 6 attack types."""
    nodes, node_map, pos, edge_pdr, rep, poa, gossip, lora, byz_nodes, scores = \
        build_mesh(10, bus, n_byzantine=1)
    viz.set_mesh(pos, edge_pdr, scores)
    bus.post({"type": "mesh_reset", "scenario": "A: N=10  1 Byzantine (PKI reject)"})

    honest = [n for n in nodes if n not in byz_nodes]

    for node in honest[:3]:
        if done.is_set(): return
        result = _propose(node, "GPS_UPDATE", {"lat": 51.5, "lon": -0.1})
        if result.approved:
            _gossip_after_commit(node, node_map, pos, gossip, lora)
        bus.sleep(0.6)

    attacks = ["invalid_signature", "tampered_payload",
               "impossible_values", "gps_teleport",
               "replay_attack", "counter_manipulation"]
    for byz in byz_nodes:
        for atk in attacks:
            if done.is_set(): return
            try:
                block = byz.attack(atk)
            except Exception:
                continue
            # Propose through the hooked coordinator directly
            peers = [n for n in nodes if n is not byz]
            poa.propose(block, byz, peers)
            bus.sleep(0.5)


def scenario_b(bus: EventBus, viz: Visualizer, done: threading.Event):
    """N=20, 3 Byzantine — mass rejection."""
    nodes, node_map, pos, edge_pdr, rep, poa, gossip, lora, byz_nodes, scores = \
        build_mesh(20, bus, n_byzantine=3)
    viz.set_mesh(pos, edge_pdr, scores)
    bus.post({"type": "mesh_reset", "scenario": "B: N=20  3 Byzantine"})

    honest = [n for n in nodes if n not in byz_nodes]

    for node in honest[:5]:
        if done.is_set(): return
        result = _propose(node, "GPS_UPDATE", {"lat": 51.5, "lon": -0.1})
        if result.approved:
            _gossip_after_commit(node, node_map, pos, gossip, lora)
        bus.sleep(0.4)

    for byz in byz_nodes:
        for atk in ["invalid_signature", "tampered_payload", "impossible_values"]:
            if done.is_set(): return
            try:
                block = byz.attack(atk)
            except Exception:
                continue
            peers = [n for n in nodes if n is not byz]
            poa.propose(block, byz, peers)
            bus.sleep(0.4)


def scenario_c(bus: EventBus, viz: Visualizer, done: threading.Event):
    """N=50, 5 node failures — gossip delivery with dead nodes."""
    nodes, node_map, pos, edge_pdr, rep, poa, gossip, lora, _, scores = \
        build_mesh(50, bus, area=200.0)
    viz.set_mesh(pos, edge_pdr, scores)
    bus.post({"type": "mesh_reset", "scenario": "C: N=50  normal operation"})

    for node in nodes[:8]:
        if done.is_set(): return
        result = _propose(node, "GPS_UPDATE", {"lat": 51.5, "lon": -0.1})
        if result.approved:
            _gossip_after_commit(node, node_map, pos, gossip, lora)
        bus.sleep(0.25)

    # simulate 5 failures by removing from node_map + gossip routing
    failed_ids = list(node_map.keys())[-5:]
    bus.post({"type": "mesh_reset",
              "scenario": "C: N=50  5 node failures"})
    for fid in failed_ids:
        node_map.pop(fid, None)

    for node in list(node_map.values())[:6]:
        if done.is_set(): return
        result = _propose(node, "GPS_UPDATE", {"lat": 51.5, "lon": -0.1})
        if result.approved:
            _gossip_after_commit(node, node_map, pos, gossip, lora)
        bus.sleep(0.35)


def scenario_d(bus: EventBus, viz: Visualizer, done: threading.Event):
    """N=20 partition + heal — chain sync."""
    nodes, node_map, pos, edge_pdr, rep, poa, gossip, lora, _, scores = \
        build_mesh(20, bus)
    viz.set_mesh(pos, edge_pdr, scores)
    bus.post({"type": "mesh_reset", "scenario": "D: N=20  group A proposing"})

    half_a   = nodes[:10]
    half_b   = nodes[10:]
    map_a    = {n.node_id: n for n in half_a}
    map_b    = {n.node_id: n for n in half_b}

    for node in half_a[:3]:
        if done.is_set(): return
        result = _propose(node, "GPS_UPDATE", {"lat": 51.5, "lon": -0.1})
        if result.approved:
            gossip.broadcast(node.node_id, node.chain.blocks[-1], map_a, pos, lora)
        bus.sleep(0.5)

    bus.post({"type": "mesh_reset", "scenario": "D: N=20  group B proposing"})

    for node in half_b[:3]:
        if done.is_set(): return
        result = _propose(node, "GPS_UPDATE", {"lat": 51.6, "lon": -0.1})
        if result.approved:
            gossip.broadcast(node.node_id, node.chain.blocks[-1], map_b, pos, lora)
        bus.sleep(0.5)

    bus.post({"type": "mesh_reset", "scenario": "D: N=20  partition healed"})

    # Sync group B from group A
    for node in half_b:
        if done.is_set(): return
        node.chain.sync_missing(half_a[0].chain)
    bus.sleep(1.0)
    bus.post({"type": "block_committed", "node_id": "mesh",
              "index": -1, "reason": "Partition healed — chains synced"})


def scenario_e(bus: EventBus, viz: Visualizer, done: threading.Event):
    """N=20 FL: 10 rounds of DP FedAvg, tracking convergence."""
    nodes, node_map, pos, edge_pdr, rep, poa, gossip, lora, _, scores = \
        build_mesh(20, bus)
    viz.set_mesh(pos, edge_pdr, scores)
    bus.post({"type": "mesh_reset", "scenario": "E: N=20  FL convergence (10 rounds)"})

    # Each node has a target: first 10 pull toward +1, last 10 toward -1
    targets = [1.0 if i < 10 else -1.0 for i in range(20)]
    models  = [LocalModel(np.full(8, targets[i], dtype=np.float64)
                          + np.random.default_rng(i).normal(0, 0.5, 8))
               for i in range(20)]

    for rnd in range(1, 11):
        if done.is_set(): return

        # local gradient step toward target
        for i, m in enumerate(models):
            grad = np.sign(targets[i] - m.weights) * 0.3
            m.weights += grad + np.random.normal(0, 0.05, 8)

        weights_list = [m.weights.copy() for m in models]
        global_w     = fedavg(weights_list)
        global_w     = add_gaussian_noise(global_w, epsilon=10.0, delta=1e-5, C=1.0)
        delta        = float(np.linalg.norm(global_w))

        bus.post({"type": "fl_round", "round": rnd, "delta": delta})

        for m in models:
            m.weights = global_w.copy()

        # Propose FL_ROUND block
        proposer     = nodes[rnd % len(nodes)]
        weight_hash  = hashlib.sha256(global_w.tobytes()).hexdigest()
        result       = _propose(proposer, "FL_ROUND",
                                {"weight_hash": weight_hash, "round": rnd},
                                anomaly=0.05)
        if result.approved:
            _gossip_after_commit(proposer, node_map, pos, gossip, lora)

        bus.sleep(0.7)


SCENARIOS = [scenario_a, scenario_b, scenario_c, scenario_d, scenario_e]


# ------------------------------------------------------------------ #
#  Entry point                                                         #
# ------------------------------------------------------------------ #

def main():
    bus = EventBus()

    # Starter mesh for visualizer init
    _, _, pos0, ep0, _, _, _, _, _, sc0 = build_mesh(20, bus)

    viz = Visualizer(bus)
    viz.set_mesh(pos0, ep0, sc0)

    scenario_idx    = 0
    done_event      = threading.Event()
    current_thread  = None

    def launch(idx):
        nonlocal current_thread, done_event
        done_event.set()
        if current_thread and current_thread.is_alive():
            current_thread.join(timeout=2.0)
        done_event = threading.Event()
        fn = SCENARIOS[idx % len(SCENARIOS)]
        t  = threading.Thread(target=fn, args=(bus, viz, done_event), daemon=True)
        t.start()
        return t

    current_thread = launch(0)

    running = True
    while running:
        result = viz.tick()
        if result == "quit":
            running = False
        elif result == "next":
            scenario_idx  += 1
            current_thread = launch(scenario_idx)

    done_event.set()
    viz.close()


if __name__ == "__main__":
    main()
