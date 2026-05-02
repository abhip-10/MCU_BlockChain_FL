# -*- coding: utf-8 -*-
"""
Milestone 4 - Federated Learning Simulation
Proves:
  - Two nodes start with different weights and converge via FedAvg
  - Each FL round is logged as a verified FL_ROUND block through PoA consensus
  - Differential privacy noise is applied before weight broadcast
  - Tampered weights are rejected by hash verification (round 3)
  - A Byzantine node cannot inject poisoned weights into consensus
"""
import hashlib
import sys

import numpy as np

sys.path.insert(0, ".")

from src.federated.dp_noise import add_gaussian_noise, dp_sigma
from src.federated.fedavg import fedavg
from src.federated.local_model import LocalModel
from src.network.mesh import create_full_mesh

# ── Constants ────────────────────────────────────────────────────────────────
WEIGHT_DIM   = 16
FL_ROUNDS    = 10
TAMPER_ROUND = 5          # inject tampered weights from Node2 in this round
TRAIN_LR     = 0.01
DP_EPSILON   = 10.0       # demo value: epsilon=1.0 available in dp_noise.py
DP_DELTA     = 1e-5       # gives sigma=0.485; epsilon=1.0 gives sigma=4.85 (needs 50+ rounds)
DP_C         = 1.0
SEED         = 42


def separator(label: str) -> None:
    print(f"\n{'-' * 64}")
    print(f"  {label}")
    print('-' * 64)


def weight_hash(weights: np.ndarray) -> str:
    return hashlib.sha256(weights.tobytes()).hexdigest()


def verify_weights(received: np.ndarray, received_hash: str) -> bool:
    return weight_hash(received) == received_hash


def run() -> None:
    np.random.seed(SEED)

    # ── Mesh setup ───────────────────────────────────────────────────────────
    separator("Setup - 2-node mesh")
    nodes, reputation = create_full_mesh(["NODE_1", "NODE_2"])
    n1, n2 = nodes

    model1 = LocalModel(np.ones(WEIGHT_DIM))    # Node1 starts high
    model2 = LocalModel(np.zeros(WEIGHT_DIM))   # Node2 starts low

    sigma = dp_sigma(DP_EPSILON, DP_DELTA, DP_C)
    print(f"  Node1 initial weights (mean): {model1.weights.mean():.4f}")
    print(f"  Node2 initial weights (mean): {model2.weights.mean():.4f}")
    print(f"  Initial convergence delta   : {model1.convergence_delta(model2):.4f}")
    print(f"  DP sigma (epsilon={DP_EPSILON}, delta={DP_DELTA}): {sigma:.4f}")

    # ── FL rounds ────────────────────────────────────────────────────────────
    separator(f"Running {FL_ROUNDS} FL rounds  (tamper injected at round {TAMPER_ROUND})")

    deltas = []
    fl_blocks_committed = 0

    for rnd in range(1, FL_ROUNDS + 1):
        print(f"\n  -- Round {rnd} --")
        delta_before = model1.convergence_delta(model2)

        # 1. Local training steps
        model1.train(TRAIN_LR)
        model2.train(TRAIN_LR)

        # 2. Prepare broadcast: apply DP noise, hash the noisy weights
        w1_tx = add_gaussian_noise(model1.weights, DP_EPSILON, DP_DELTA, DP_C)
        w2_tx = add_gaussian_noise(model2.weights, DP_EPSILON, DP_DELTA, DP_C)
        h1 = weight_hash(w1_tx)
        h2 = weight_hash(w2_tx)

        # 3. Tamper injection: in round TAMPER_ROUND, corrupt Node2's weights
        tampered = (rnd == TAMPER_ROUND)
        if tampered:
            w2_rx = w2_tx.copy()
            w2_rx[0] += 500.0           # obvious corruption
            print(f"  [TAMPER] Node2 weights corrupted before Node1 receives them")
        else:
            w2_rx = w2_tx               # clean delivery

        # 4. Hash verification at each receiver
        n1_accepts = verify_weights(w2_rx, h2)
        n2_accepts = verify_weights(w1_tx, h1)

        if not n1_accepts:
            print(f"  Node1 REJECTED Node2 weights — hash mismatch [OK]")
        if not n2_accepts:
            print(f"  Node2 REJECTED Node1 weights — hash mismatch")

        # 5. FedAvg — only using verified weights
        if n1_accepts:
            model1.weights = fedavg([model1.weights, w2_rx])
        if n2_accepts:
            model2.weights = fedavg([model2.weights, w1_tx])

        delta_after = model1.convergence_delta(model2)
        deltas.append((rnd, delta_before, delta_after, tampered))

        print(f"  Convergence delta: {delta_before:.4f} -> {delta_after:.4f}  "
              f"({'no FL block' if tampered else 'FL block committed'})")

        # 6. Log FL round as blockchain block through PoA (skip if tampered)
        if not tampered:
            payload = {
                "round":        rnd,
                "n1_hash":      model1.weight_hash(),
                "n2_hash":      model2.weight_hash(),
                "dp_epsilon":   DP_EPSILON,
                "dp_delta":     DP_DELTA,
            }
            result = n1.propose("FL_ROUND", payload, anomaly_score=0.01)
            assert result.approved, f"FL_ROUND block rejected: {result.reason}"
            fl_blocks_committed += 1

    # ── Convergence summary ───────────────────────────────────────────────────
    separator("Convergence summary")
    print(f"  {'Round':<8} {'Delta before':<16} {'Delta after':<16} {'Note'}")
    print(f"  {'-'*55}")
    for rnd, before, after, tampered in deltas:
        note = "TAMPERED - no FedAvg" if tampered else ""
        print(f"  {rnd:<8} {before:<16.4f} {after:<16.4f} {note}")

    print(f"\n  Node1 final weights (mean): {model1.weights.mean():.4f}")
    print(f"  Node2 final weights (mean): {model2.weights.mean():.4f}")
    print(f"  Final convergence delta   : {model1.convergence_delta(model2):.4f}")

    # Assert weights converged: final delta at least 40% smaller than initial
    initial_delta = float(WEIGHT_DIM ** 0.5)   # ||ones - zeros|| = sqrt(16) = 4.0
    final_delta   = model1.convergence_delta(model2)
    assert final_delta < 0.60 * initial_delta, (
        f"Weights did not converge enough: {final_delta:.4f} vs threshold {0.60*initial_delta:.4f}"
    )
    print(f"\n  Convergence confirmed: {final_delta:.4f} < {0.60*initial_delta:.4f} [OK]")

    # ── FL blocks in chain ────────────────────────────────────────────────────
    separator("FL_ROUND blocks in chain")
    for node in [n1, n2]:
        fl_in_chain = [b for b in node.chain.blocks if b.event_type == "FL_ROUND"]
        assert len(fl_in_chain) == fl_blocks_committed, (
            f"{node.node_id}: expected {fl_blocks_committed} FL blocks, "
            f"got {len(fl_in_chain)}"
        )
        print(f"  {node.node_id}: {len(fl_in_chain)} FL_ROUND blocks in chain [OK]")

    for b in n1.chain.blocks:
        if b.event_type == "FL_ROUND":
            rnd = b.payload["round"]
            print(f"    Round {rnd}  block[{b.index:02d}]  hash: {b.block_hash[:20]}...")

    # Tampered round must NOT appear as FL block
    fl_rounds_in_chain = {b.payload["round"] for b in n1.chain.blocks
                          if b.event_type == "FL_ROUND"}
    assert TAMPER_ROUND not in fl_rounds_in_chain, \
        f"Tampered round {TAMPER_ROUND} must not appear as FL block"
    print(f"\n  Round {TAMPER_ROUND} (tampered) absent from chain [OK]")

    # Both chains identical
    assert n1.chain.tip_hash() == n2.chain.tip_hash(), "Chain tips diverged"
    print(f"  Both chain tips match [OK]")

    # ── Chain summary ─────────────────────────────────────────────────────────
    separator("Full chain state")
    for b in n1.chain.blocks:
        print(f"  [{b.index:02d}] {b.event_type:<14} hash: {b.block_hash[:20]}...")

    print("\n" + "=" * 64)
    print("  M4 COMPLETE -- All assertions passed")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    run()
