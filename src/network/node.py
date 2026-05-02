import time

from src.blockchain.block import Block, make_genesis
from src.blockchain.chain import Chain
from src.blockchain.crypto import generate_keypair
from src.consensus import validator as v
from src.consensus.poa import PoACoordinator, ConsensusResult
from src.consensus.reputation import ReputationEngine


class VirtualNode:
    def __init__(self, node_id: str, reputation: ReputationEngine) -> None:
        self.node_id = node_id
        self.private_key, self.public_key_pem = generate_keypair()
        self.chain = Chain(public_keys={node_id: self.public_key_pem})
        self.peers: list["VirtualNode"] = []
        self.reputation = reputation
        self._poa = PoACoordinator(reputation)
        self._frame_counter = 0

    def register_peer(self, peer: "VirtualNode") -> None:
        if peer not in self.peers:
            self.peers.append(peer)
            self.chain.register_public_key(peer.node_id, peer.public_key_pem)

    def init_genesis(self) -> Block:
        """Create the shared genesis block (call once on network coordinator)."""
        genesis = make_genesis(self.node_id, self.private_key)
        self.chain.append(genesis)
        return genesis

    def receive_genesis(self, genesis: Block) -> None:
        """Accept a genesis block without consensus (network bootstrap only)."""
        self.chain.append(genesis)

    def create_block(self, event_type: str, payload: dict,
                     anomaly_score: float = 0.05) -> Block:
        self._frame_counter += 1
        b = Block(
            index=len(self.chain.blocks),
            timestamp=time.time(),
            prev_hash=self.chain.tip_hash(),
            frame_counter=self._frame_counter,
            node_id=self.node_id,
            event_type=event_type,
            payload=payload,
            anomaly_score=anomaly_score,
        )
        b.sign_block(self.private_key)
        return b

    def propose(self, event_type: str, payload: dict,
                anomaly_score: float = 0.05) -> ConsensusResult:
        """Create a block and run PoA consensus with all peers."""
        block = self.create_block(event_type, payload, anomaly_score)
        return self._poa.propose(block, proposer_node=self, peers=self.peers)

    def propose_raw(self, block: Block) -> ConsensusResult:
        """Propose an already-constructed block (used for tamper tests)."""
        return self._poa.propose(block, proposer_node=self, peers=self.peers)

    def receive_proposal(self, block: Block) -> tuple[bool, str]:
        """Validate a peer's proposed block and return a vote."""
        return v.validate(block, self.chain)
