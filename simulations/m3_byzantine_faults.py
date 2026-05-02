# -*- coding: utf-8 -*-
"""
Milestone 3 - Byzantine Fault Tolerance
Proves that all 6 attack scenarios are rejected by honest nodes,
the Byzantine node is automatically flagged, and honest consensus
continues uninterrupted after every attack.

Network setup:
  Phase 1: N1 <-> N2 only (2 honest blocks committed, Byz earns no rewards)
  Phase 2: Byz joins, syncs chain, commits 1 honest block (score 0.55)
  Phase 3: 6 attacks -> Byz flagged after 3rd rejection (score drops to 0.10)
  Phase 4: N1 + N2 commit 5 more blocks uninterrupted
  Phase 5: Assert Byz blocks in all honest chains = exactly 1 (the honest one)
"""
import sys

sys.path.insert(0, ".")

from src.byzantine.attacker import ByzantineNode
from src.consensus.reputation import ReputationEngine
from src.network.node import VirtualNode


# ── Expected check for each scenario ────────────────────────────────────────
SCENARIOS = [
    ("invalid_signature",    "invalid_signature"),
    ("tampered_payload",     "invalid_hash"),
    ("impossible_values",    "anomaly_score_too_high"),
    ("gps_teleport",         "anomaly_score_too_high"),
    ("replay_attack",        "replay_or_counter_manipulation"),
    ("counter_manipulation", "replay_or_counter_manipulation"),
]


def separator(label: str) -> None:
    print(f"\n{'-' * 64}")
    print(f"  {label}")
    print('-' * 64)


def show_tips(nodes: list) -> None:
    for n in nodes:
        print(f"  {n.node_id:<12} tip[{n.chain.tip_index():02d}]: {n.chain.tip_hash()[:22]}...")


def assert_tips_match(nodes: list) -> None:
    tips = [n.chain.tip_hash() for n in nodes]
    assert len(set(tips)) == 1, "Chain tips diverged: " + str(tips)


def run() -> None:
    reputation = ReputationEngine()

    # ── Phase 1: Build 2-node honest mesh (Byz not connected) ───────────────
    separator("Phase 1 - Honest mesh bootstrap (N1 <-> N2)")

    n1  = VirtualNode("NODE_1",    reputation)
    n2  = VirtualNode("NODE_2",    reputation)
    byz = ByzantineNode("BYZANTINE", reputation)

    genesis = n1.init_genesis()
    n2.receive_genesis(genesis)
    byz.receive_genesis(genesis)

    n1.register_peer(n2)
    n2.register_peer(n1)

    r = n1.propose("GPS_UPDATE", {"lat": 18.5204, "lon": 73.8567})
    assert r.approved
    r = n2.propose("GPS_UPDATE", {"lat": 18.5210, "lon": 73.8571})
    assert r.approved

    print(f"  N1 and N2 committed 2 blocks (Byz not involved)")
    print(f"  Byz reputation score: {reputation.score('BYZANTINE'):.2f}  (no rewards earned)")

    # ── Phase 2: Add Byz, sync chain, establish frame counter ───────────────
    separator("Phase 2 - Byzantine node joins mesh")

    n1.register_peer(byz)
    n2.register_peer(byz)
    byz.register_peer(n1)
    byz.register_peer(n2)
    byz.chain.sync_missing(n1.chain)

    print(f"  Byz chain synced — tip[{byz.chain.tip_index():02d}]: {byz.chain.tip_hash()[:22]}...")
    assert_tips_match([n1, n2, byz])

    r = byz.propose("GPS_UPDATE", {"lat": 18.5215, "lon": 73.8575})
    assert r.approved, "Expected Byz honest block to be approved"
    print(f"  Byz honest block committed — frame_counter=1 now known to all chains")
    print(f"  Byz reputation score: {reputation.score('BYZANTINE'):.2f}  (proposer reward)")
    assert_tips_match([n1, n2, byz])

    # ── Phase 3: 6 attack scenarios ─────────────────────────────────────────
    separator("Phase 3 - Byzantine attack scenarios")

    flagged_at = None

    for i, (scenario, expected_reason) in enumerate(SCENARIOS, start=1):
        chain_len_before = len(n1.chain.blocks)
        bad_block = byz.attack(scenario)
        result = byz.propose_raw(bad_block)

        score_after = reputation.score("BYZANTINE")
        flagged = reputation.is_flagged("BYZANTINE")
        flag_marker = "  [FLAGGED]" if flagged and flagged_at is None else ""
        if flagged and flagged_at is None:
            flagged_at = i

        status = "REJECTED [OK]" if not result.approved else "APPROVED [FAIL]"
        print(f"\n  Attack {i}: {scenario}")
        print(f"    Reason  : {result.reason}")
        print(f"    Expected: {expected_reason}")
        print(f"    Status  : {status}")
        print(f"    Byz score: {score_after:.2f}{flag_marker}")

        assert not result.approved, f"Attack {i} should have been rejected"
        assert result.reason == expected_reason, (
            f"Attack {i}: expected reason '{expected_reason}', got '{result.reason}'"
        )
        assert len(n1.chain.blocks) == chain_len_before, \
            f"Attack {i}: bad block entered chain"
        assert len(n2.chain.blocks) == chain_len_before, \
            f"Attack {i}: bad block entered chain"

    print(f"\n  Byzantine node flagged after attack #{flagged_at} [OK]")
    assert reputation.is_flagged("BYZANTINE"), "Byzantine node must be flagged after attacks"
    assert_tips_match([n1, n2, byz])

    # ── Phase 4: Honest mesh continues uninterrupted ────────────────────────
    separator("Phase 4 - Honest nodes continue after Byzantine attacks")

    post_attack_events = [
        (n1, "GPS_UPDATE", {"lat": 18.5220, "lon": 73.8580}),
        (n2, "FALL",       {"accel_mag": 3.1, "duration_still": 3.5}),
        (n1, "GPS_UPDATE", {"lat": 18.5225, "lon": 73.8585}),
        (n2, "GPS_UPDATE", {"lat": 18.5230, "lon": 73.8590}),
        (n1, "DISTRESS",   {"hr": 148, "spo2": 87}),
    ]

    for node, event, payload in post_attack_events:
        r = node.propose(event, payload)
        assert r.approved, f"Honest block from {node.node_id} should be approved"
        print(f"  {node.node_id} committed {event:<14} tip[{n1.chain.tip_index():02d}]")

    assert_tips_match([n1, n2, byz])
    print("\n  All 5 post-attack honest blocks committed [OK]")

    # ── Phase 5: Verify Byzantine contamination ──────────────────────────────
    separator("Phase 5 - Chain integrity check")

    for node in [n1, n2]:
        byz_blocks = [b for b in node.chain.blocks if b.node_id == "BYZANTINE"]
        assert len(byz_blocks) == 1, (
            f"{node.node_id} chain has {len(byz_blocks)} Byz blocks, expected 1"
        )
        print(f"  {node.node_id}: Byz blocks in chain = {len(byz_blocks)} (honest block only) [OK]")

    # ── Final summary ────────────────────────────────────────────────────────
    separator("Chain summary")
    print(f"  Total committed blocks: {len(n1.chain.blocks)}")
    for b in n1.chain.blocks:
        owner = "BYZ" if b.node_id == "BYZANTINE" else b.node_id
        print(f"  [{b.index:02d}] {b.event_type:<14} node={owner:<10} hash: {b.block_hash[:20]}...")

    separator("Final reputation scores")
    for nid, score in reputation.all_scores().items():
        flag = "  [FLAGGED]" if reputation.is_flagged(nid) else ""
        print(f"  {nid:<12}: {score:.2f}{flag}")

    print("\n" + "=" * 64)
    print("  M3 COMPLETE -- All assertions passed")
    print("=" * 64 + "\n")


if __name__ == "__main__":
    run()
