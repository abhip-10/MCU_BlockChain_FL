from src.blockchain.block import Block
from src.blockchain.merkle import MerkleTree


class Chain:
    def __init__(self, public_keys: dict[str, bytes]):
        """public_keys: node_id → public_key_pem"""
        self.blocks: list[Block] = []
        self.public_keys = public_keys
        self._seen_frame_counters: dict[str, int] = {}

    def register_public_key(self, node_id: str, public_key_pem: bytes) -> None:
        self.public_keys[node_id] = public_key_pem

    def append(self, block: Block) -> None:
        self.blocks.append(block)
        self._seen_frame_counters[block.node_id] = block.frame_counter

    def validate(self) -> tuple[bool, int]:
        """Returns (valid, first_invalid_index). -1 means fully valid."""
        for i, block in enumerate(self.blocks):
            expected_prev = "0" * 64 if i == 0 else self.blocks[i - 1].block_hash

            if block.compute_hash() != block.block_hash:
                return False, i

            if block.prev_hash != expected_prev:
                return False, i

            pub = self.public_keys.get(block.node_id)
            if pub and not block.verify_signature(pub):
                return False, i

        return True, -1

    def last_frame_counter(self, node_id: str) -> int:
        return self._seen_frame_counters.get(node_id, -1)

    def tip_hash(self) -> str:
        return self.blocks[-1].block_hash if self.blocks else "0" * 64

    def tip_index(self) -> int:
        return self.blocks[-1].index if self.blocks else -1

    def merkle_root(self) -> str:
        return MerkleTree([b.block_hash for b in self.blocks]).root

    def sync_missing(self, peer: "Chain") -> int:
        """Append blocks from peer that this chain is missing. Returns count synced."""
        own_tip = self.tip_index()
        missing = [b for b in peer.blocks if b.index > own_tip]
        for b in missing:
            self.append(b)
        return len(missing)
