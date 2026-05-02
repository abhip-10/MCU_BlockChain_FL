import time

from src.blockchain.block import Block
from src.blockchain.crypto import generate_keypair
from src.network.node import VirtualNode


class ByzantineNode(VirtualNode):
    """
    Extends VirtualNode with 6 attack scenarios.
    Holds a second keypair used only for invalid-signature attacks.
    All other behaviour (chain, peers, reputation) is inherited unchanged.
    """

    def __init__(self, node_id: str, reputation) -> None:
        super().__init__(node_id, reputation)
        self._wrong_key, _ = generate_keypair()

    def attack(self, scenario: str) -> Block:
        """
        Build a tampered block for the given scenario.
        Uses self.chain.tip_hash() as prev_hash so check 3 passes,
        isolating each attack to exactly the check it targets.

        Scenarios and the check they trigger:
          invalid_signature    -> check 1 (wrong signing key)
          tampered_payload     -> check 2 (payload mutated after signing)
          impossible_values    -> check 5 (anomaly_score 0.95 > 0.7)
          gps_teleport         -> check 5 (anomaly_score 0.90 > 0.7)
          replay_attack        -> check 4 (reuses last committed frame_counter)
          counter_manipulation -> check 4 (frame_counter set to 0)
        """
        prev = self.chain.tip_hash()
        idx  = len(self.chain.blocks)

        if scenario == "invalid_signature":
            self._frame_counter += 1
            b = Block(
                index=idx, timestamp=time.time(), prev_hash=prev,
                frame_counter=self._frame_counter, node_id=self.node_id,
                event_type="GPS_UPDATE",
                payload={"lat": 18.5204, "lon": 73.8567},
                anomaly_score=0.05,
            )
            b.sign_block(self._wrong_key)   # wrong key — check 1 fails
            return b

        if scenario == "tampered_payload":
            self._frame_counter += 1
            b = Block(
                index=idx, timestamp=time.time(), prev_hash=prev,
                frame_counter=self._frame_counter, node_id=self.node_id,
                event_type="GPS_UPDATE",
                payload={"lat": 18.5204, "lon": 73.8567},
                anomaly_score=0.05,
            )
            b.sign_block(self.private_key)
            b.payload["lat"] = 99.9999      # mutate after signing — check 2 fails
            return b

        if scenario == "impossible_values":
            self._frame_counter += 1
            b = Block(
                index=idx, timestamp=time.time(), prev_hash=prev,
                frame_counter=self._frame_counter, node_id=self.node_id,
                event_type="DISTRESS",
                payload={"hr": 999, "spo2": 150},
                anomaly_score=0.95,         # TinyML gate — check 5 fails
            )
            b.sign_block(self.private_key)
            return b

        if scenario == "gps_teleport":
            self._frame_counter += 1
            b = Block(
                index=idx, timestamp=time.time(), prev_hash=prev,
                frame_counter=self._frame_counter, node_id=self.node_id,
                event_type="GPS_UPDATE",
                payload={"lat": 48.8566, "lon": 2.3522},   # Paris jump from Pune
                anomaly_score=0.90,         # check 5 fails
            )
            b.sign_block(self.private_key)
            return b

        if scenario == "replay_attack":
            # Reuse the last committed frame_counter (already seen by honest nodes).
            # Correct prev_hash so check 3 passes; stale counter caught by check 4.
            last = self.chain.last_frame_counter(self.node_id)
            b = Block(
                index=idx, timestamp=time.time(), prev_hash=prev,
                frame_counter=last,         # old counter — check 4 fails
                node_id=self.node_id,
                event_type="GPS_UPDATE",
                payload={"lat": 18.5204, "lon": 73.8567},
                anomaly_score=0.05,
            )
            b.sign_block(self.private_key)
            return b

        if scenario == "counter_manipulation":
            b = Block(
                index=idx, timestamp=time.time(), prev_hash=prev,
                frame_counter=0,            # well below last seen — check 4 fails
                node_id=self.node_id,
                event_type="GPS_UPDATE",
                payload={"lat": 18.5204, "lon": 73.8567},
                anomaly_score=0.05,
            )
            b.sign_block(self.private_key)
            return b

        raise ValueError(f"Unknown attack scenario: {scenario}")
