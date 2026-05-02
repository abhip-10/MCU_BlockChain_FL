import hashlib
from typing import Optional


def _sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()


class MerkleTree:
    def __init__(self, block_hashes: list[str]):
        self.leaves = list(block_hashes)
        self._root = self._build(self.leaves) if self.leaves else ""

    def _build(self, layer: list[str]) -> str:
        if len(layer) == 1:
            return layer[0]
        if len(layer) % 2 == 1:
            layer = layer + [layer[-1]]  # duplicate last if odd
        next_layer = [_sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        return self._build(next_layer)

    @property
    def root(self) -> str:
        return self._root

    def get_proof(self, index: int) -> list[tuple[str, str]]:
        """Returns list of (sibling_hash, position) where position is 'left'|'right'."""
        layer = list(self.leaves)
        proof = []
        while len(layer) > 1:
            if len(layer) % 2 == 1:
                layer = layer + [layer[-1]]
            sibling_index = index ^ 1
            position = "left" if sibling_index < index else "right"
            proof.append((layer[sibling_index], position))
            index //= 2
            layer = [_sha256(layer[i] + layer[i + 1]) for i in range(0, len(layer), 2)]
        return proof

    @staticmethod
    def verify_proof(leaf_hash: str, proof: list[tuple[str, str]], root: str) -> bool:
        current = leaf_hash
        for sibling, position in proof:
            if position == "left":
                current = _sha256(sibling + current)
            else:
                current = _sha256(current + sibling)
        return current == root
