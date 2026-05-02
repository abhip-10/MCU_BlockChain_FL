# -*- coding: utf-8 -*-
"""
Milestone 2 - PoA Consensus: 2 Virtual Nodes
Proves that:
  - Valid blocks from either node enter both chains
  - Both chain tips stay identical after every commit
  - A tampered block (wrong prev_hash) is rejected before entering any chain
"""
import sys

sys.path.insert(0, ".")

from src.blockchain.block import Block
from src.network.mesh import create_full_mesh


def separator(label: str) -> None:
    print(f"\n{'-' * 62}")
    print(f"  {label}")
    print('-' * 62)


def tips(nodes) -> None:
    for n in nodes:
        print(f"  {n.node_id}  tip[{n.chain.tip_index():02d}]: {n.chain.tip_hash()[:24]}...")


def assert_tips_match(nodes) -> None:
    hashes = [n.chain.tip_hash() for n in nodes]
    assert len(set(hashes)) == 1, (
        f"Chain tips diverged!\n" + "\n".join(f"  {n.node_id}: {h}" for n, h in zip(nodes, hashes))
    )
    print("  Chain tips match [OK]")


def print_result(result) -> None:
    status = "APPROVED" if result.approved else "REJECTED"
    print(f"  Result   : {status}  ({result.reason})")
    print(f"  Votes    : {result.vote_tally}")
    print(f"  Latency  : {result.latency_ms:.3f} ms")


def run() -> None:
    nodes, reputation = create_full_mesh(["NODE_1", "NODE_2"])
    node1, node2 = nodes

    # ---------------------------------------------------------------
    # Scenario 1: Node1 proposes valid GPS_UPDATE
    # ---------------------------------------------------------------
    separator("Scenario 1 - Node1 proposes valid GPS_UPDATE")
    result = node1.propose(
        "GPS_UPDATE",
        {"lat": 18.5204, "lon": 73.8567, "alt": 560},
    )
    print_result(result)
    assert result.approved, "Expected approval"
    tips(nodes)
    assert_tips_match(nodes)

    # ---------------------------------------------------------------
    # Scenario 2: Node2 proposes valid FALL block
    # ---------------------------------------------------------------
    separator("Scenario 2 - Node2 proposes valid FALL")
    result = node2.propose(
        "FALL",
        {"accel_mag": 3.2, "duration_still": 4.1},
    )
    print_result(result)
    assert result.approved, "Expected approval"
    tips(nodes)
    assert_tips_match(nodes)

    # ---------------------------------------------------------------
    # Scenario 3: Node1 proposes DISTRESS block
    # ---------------------------------------------------------------
    separator("Scenario 3 - Node1 proposes valid DISTRESS")
    result = node1.propose(
        "DISTRESS",
        {"hr": 148, "spo2": 87, "accel_mag": 3.4},
    )
    print_result(result)
    assert result.approved, "Expected approval"
    tips(nodes)
    assert_tips_match(nodes)

    # ---------------------------------------------------------------
    # Scenario 4: Block with wrong prev_hash (rejected)
    # ---------------------------------------------------------------
    separator("Scenario 4 - Node2 proposes block with wrong prev_hash")
    node2._frame_counter += 1
    bad_block = Block(
        index=len(node2.chain.blocks),
        timestamp=__import__("time").time(),
        prev_hash="dead" * 16,          # deliberately wrong
        frame_counter=node2._frame_counter,
        node_id=node2.node_id,
        event_type="GPS_UPDATE",
        payload={"lat": 18.5220, "lon": 73.8580},
        anomaly_score=0.05,
    )
    bad_block.sign_block(node2.private_key)

    chain_len_before = len(node1.chain.blocks)
    result = node2.propose_raw(bad_block)
    print_result(result)
    assert not result.approved, "Expected rejection"
    assert result.reason == "invalid_prev_hash", f"Wrong reason: {result.reason}"
    assert len(node1.chain.blocks) == chain_len_before, "Bad block must not enter chain"
    print("  Bad block did not enter any chain [OK]")
    tips(nodes)
    assert_tips_match(nodes)

    # ---------------------------------------------------------------
    # Scenario 5: Block with high anomaly score (rejected)
    # ---------------------------------------------------------------
    separator("Scenario 5 - Node1 proposes block with anomaly_score 0.95")
    # Frame counter was incremented on the rejected block, need to go higher
    node1._frame_counter += 1
    anomaly_block = Block(
        index=len(node1.chain.blocks),
        timestamp=__import__("time").time(),
        prev_hash=node1.chain.tip_hash(),
        frame_counter=node1._frame_counter,
        node_id=node1.node_id,
        event_type="GPS_UPDATE",
        payload={"lat": 18.5210, "lon": 73.8571},
        anomaly_score=0.95,             # above 0.7 threshold
    )
    anomaly_block.sign_block(node1.private_key)

    chain_len_before = len(node1.chain.blocks)
    result = node1.propose_raw(anomaly_block)
    print_result(result)
    assert not result.approved, "Expected rejection"
    assert result.reason == "anomaly_score_too_high", f"Wrong reason: {result.reason}"
    assert len(node1.chain.blocks) == chain_len_before, "Anomaly block must not enter chain"
    print("  Anomaly block did not enter any chain [OK]")
    tips(nodes)
    assert_tips_match(nodes)

    # ---------------------------------------------------------------
    # Final chain state
    # ---------------------------------------------------------------
    separator("Final chain state")
    print(f"  Committed blocks : {len(node1.chain.blocks)}")
    for b in node1.chain.blocks:
        print(f"  [{b.index:02d}] {b.event_type:<14} node={b.node_id}  hash: {b.block_hash[:20]}...")

    separator("Reputation scores")
    for nid, score in reputation.all_scores().items():
        flagged = "  [FLAGGED]" if reputation.is_flagged(nid) else ""
        print(f"  {nid}: {score:.2f}{flagged}")

    print("\n" + "=" * 62)
    print("  M2 COMPLETE -- All assertions passed")
    print("=" * 62 + "\n")


if __name__ == "__main__":
    run()
