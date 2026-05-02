# -*- coding: utf-8 -*-
"""
Milestone 1 - Python Blockchain Core
Single virtual node: create blocks, hash, sign, validate.
Proves tamper detection at any block index.
"""
import sys
import time

sys.path.insert(0, ".")

from src.blockchain.block import Block, make_genesis
from src.blockchain.chain import Chain
from src.blockchain.crypto import generate_keypair

EVENTS = [
    ("GPS_UPDATE",  {"lat": 18.5204, "lon": 73.8567, "alt": 560}),
    ("GPS_UPDATE",  {"lat": 18.5210, "lon": 73.8571, "alt": 562}),
    ("FALL",        {"accel_mag": 3.1, "duration_still": 4.2}),
    ("GPS_UPDATE",  {"lat": 18.5215, "lon": 73.8575, "alt": 558}),  # index 3 - tamper target
    ("DISTRESS",    {"hr": 148, "spo2": 87, "accel_mag": 3.4}),
    ("GPS_UPDATE",  {"lat": 18.5220, "lon": 73.8580, "alt": 561}),
    ("GPS_UPDATE",  {"lat": 18.5225, "lon": 73.8585, "alt": 563}),
    ("FALL",        {"accel_mag": 2.8, "duration_still": 2.1}),
    ("GPS_UPDATE",  {"lat": 18.5230, "lon": 73.8590, "alt": 559}),
    ("GPS_UPDATE",  {"lat": 18.5235, "lon": 73.8595, "alt": 560}),
]


def separator(label: str) -> None:
    print(f"\n{'-' * 60}")
    print(f"  {label}")
    print('-' * 60)


def print_chain(chain: Chain) -> None:
    for b in chain.blocks:
        print(f"  [{b.index:02d}] {b.event_type:<12}  hash: {b.block_hash[:20]}...  prev: {b.prev_hash[:20]}...")


def run() -> None:
    private_key, public_key_pem = generate_keypair()
    node_id = "NODE_1"

    chain = Chain(public_keys={node_id: public_key_pem})

    # Genesis
    separator("Creating genesis block")
    genesis = make_genesis(node_id, private_key)
    chain.append(genesis)
    print(f"  Genesis hash: {genesis.block_hash}")

    # Build 10 blocks
    separator("Adding 10 blocks")
    for fc, (event_type, payload) in enumerate(EVENTS, start=1):
        b = Block(
            index=fc,
            timestamp=time.time(),
            prev_hash=chain.tip_hash(),
            frame_counter=fc,
            node_id=node_id,
            event_type=event_type,
            payload=payload,
            anomaly_score=0.05,
        )
        b.sign_block(private_key)
        chain.append(b)
        print(f"  Block {fc:02d} | {event_type:<12} | hash: {b.block_hash[:20]}...")

    # Validate clean chain
    separator("Validating clean chain")
    valid, bad_idx = chain.validate()
    assert valid and bad_idx == -1, "Expected valid chain"
    print(f"  Result: VALID  (all {len(chain.blocks)} blocks pass) [OK]")

    # Tamper block at index 3 (GPS_UPDATE with lat field)
    # chain.blocks[3] is the FALL block; chain.blocks[4] is the GPS_UPDATE at lat=18.5215
    tamper_idx = 4
    separator(f"Tampering block[{tamper_idx}] - GPS teleport attack")
    original_payload = dict(chain.blocks[tamper_idx].payload)
    chain.blocks[tamper_idx].payload["lat"] = 99.9999
    print(f"  Original lat : {original_payload['lat']}")
    print(f"  Tampered lat : 99.9999  (impossible GPS jump)")

    valid, bad_idx = chain.validate()
    assert not valid, f"Expected invalid chain, got valid"
    assert bad_idx == tamper_idx, f"Expected failure at {tamper_idx}, got {bad_idx}"
    print(f"  Result: INVALID at index {bad_idx} [OK]")

    # Restore block
    separator(f"Restoring block[{tamper_idx}]")
    chain.blocks[tamper_idx].payload = original_payload
    print(f"  Restored lat : {chain.blocks[tamper_idx].payload['lat']}")

    valid, bad_idx = chain.validate()
    assert valid and bad_idx == -1, "Expected valid after restore"
    print(f"  Result: VALID [OK]")

    # Chain summary
    separator("Chain summary")
    print_chain(chain)
    print(f"\n  Merkle root  : {chain.merkle_root()}")
    print(f"  Chain tip    : {chain.tip_hash()}")
    print(f"  Total blocks : {len(chain.blocks)}")

    print("\n" + "=" * 60)
    print("  M1 COMPLETE -- All assertions passed")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run()
