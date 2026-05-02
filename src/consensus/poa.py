import time
from dataclasses import dataclass, field

from src.blockchain.block import Block
from src.consensus import validator as v
from src.consensus.reputation import ReputationEngine

CONSENSUS_THRESHOLD = 0.51


@dataclass
class ConsensusResult:
    approved: bool
    reason: str
    vote_tally: dict = field(default_factory=dict)   # node_id -> bool
    latency_ms: float = 0.0


class PoACoordinator:
    def __init__(self, reputation: ReputationEngine) -> None:
        self.reputation = reputation

    def propose(self, block: Block, proposer_node, peers: list) -> ConsensusResult:
        """
        Broadcast block to peers, collect votes, apply weighted threshold.
        On approval: commit block to proposer chain + all peer chains.
        On rejection: penalize proposer.
        """
        t0 = time.perf_counter()

        votes: dict[str, tuple[bool, str]] = {}
        for peer in peers:
            approved, reason = peer.receive_proposal(block)
            votes[peer.node_id] = (approved, reason)

        total_weight = sum(self.reputation.vote_weight(nid) for nid in votes)
        approve_weight = sum(
            self.reputation.vote_weight(nid)
            for nid, (approved, _) in votes.items()
            if approved
        )

        threshold_met = (
            (approve_weight / total_weight) >= CONSENSUS_THRESHOLD
            if total_weight > 0
            else False
        )

        latency_ms = (time.perf_counter() - t0) * 1000
        tally = {nid: ok for nid, (ok, _) in votes.items()}

        if threshold_met:
            proposer_node.chain.append(block)
            for peer in peers:
                peer.chain.append(block)
            for nid in votes:
                self.reputation.reward(nid)
            self.reputation.reward(proposer_node.node_id)
            return ConsensusResult(
                approved=True,
                reason="ok",
                vote_tally=tally,
                latency_ms=latency_ms,
            )

        rejection_reasons = [r for _, (ok, r) in votes.items() if not ok]
        reason = rejection_reasons[0] if rejection_reasons else "threshold_not_met"
        self.reputation.penalize(proposer_node.node_id)
        return ConsensusResult(
            approved=False,
            reason=reason,
            vote_tally=tally,
            latency_ms=latency_ms,
        )
