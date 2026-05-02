import hashlib
import json
import time
from dataclasses import dataclass, field

from src.blockchain.crypto import sign, verify


@dataclass
class Block:
    index: int
    timestamp: float
    prev_hash: str
    frame_counter: int
    node_id: str
    event_type: str       # GPS_UPDATE | FALL | DISTRESS | FL_ROUND
    payload: dict
    anomaly_score: float  # 0.0–1.0 simulated TinyML score
    block_hash: str = ""
    signature: bytes = field(default=b"", repr=False)

    def compute_hash(self) -> str:
        content = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "prev_hash": self.prev_hash,
            "frame_counter": self.frame_counter,
            "node_id": self.node_id,
            "event_type": self.event_type,
            "payload": self.payload,
            "anomaly_score": self.anomaly_score,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def sign_block(self, private_key) -> None:
        self.block_hash = self.compute_hash()
        self.signature = sign(private_key, self.block_hash.encode())

    def verify_signature(self, public_key_pem: bytes) -> bool:
        if not self.signature:
            return False
        return verify(public_key_pem, self.block_hash.encode(), self.signature)


def make_genesis(node_id: str, private_key) -> Block:
    b = Block(
        index=0,
        timestamp=time.time(),
        prev_hash="0" * 64,
        frame_counter=0,
        node_id=node_id,
        event_type="GENESIS",
        payload={},
        anomaly_score=0.0,
    )
    b.sign_block(private_key)
    return b
