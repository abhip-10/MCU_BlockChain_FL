"""
Hooked subclasses of existing src/ classes.
Fire EventBus events without modifying the originals.
"""
from collections import deque

from src.blockchain.block import Block
from src.consensus.reputation import ReputationEngine
from src.consensus.poa import PoACoordinator
from src.network.gossip import GossipProtocol
from src.network.lora_sim import LoRaChannel
from sim.event_bus import EventBus

GOSSIP_FANOUT = 3


class HookedReputationEngine(ReputationEngine):
    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus

    def reward(self, node_id: str) -> None:
        super().reward(node_id)
        self._bus.post({"type": "reputation_change", "node_id": node_id,
                        "score": self.score(node_id), "delta": +self.REWARD})

    def penalize(self, node_id: str) -> None:
        super().penalize(node_id)
        self._bus.post({"type": "reputation_change", "node_id": node_id,
                        "score": self.score(node_id), "delta": -self.PENALTY})


class HookedPoACoordinator(PoACoordinator):
    def __init__(self, bus: EventBus, reputation: HookedReputationEngine) -> None:
        super().__init__(reputation)
        self._bus = bus

    def propose(self, block: Block, proposer_node, peers: list):
        self._bus.post({"type": "block_proposed",
                        "proposer": block.node_id,
                        "index": block.index,
                        "event_type": block.event_type})
        self._bus.sleep(0.12)

        result = super().propose(block, proposer_node, peers)

        # fire per-vote events from the tally (votes already cast by super)
        for voter_id, approved in result.vote_tally.items():
            self._bus.post({"type": "vote_cast",
                            "voter": voter_id,
                            "proposer": block.node_id,
                            "approved": approved,
                            "reason": ""})
            self._bus.sleep(0.05)

        ev_type = "block_committed" if result.approved else "block_rejected"
        self._bus.post({"type": ev_type,
                        "node_id": block.node_id,
                        "index": block.index,
                        "reason": result.reason})
        self._bus.sleep(0.10)
        return result


class HookedGossipProtocol(GossipProtocol):
    """Replicate gossip broadcast and fire a 'gossip_hop' event per delivery attempt."""

    def __init__(self, bus: EventBus) -> None:
        super().__init__()
        self._bus = bus

    def broadcast(self, origin_id: str, block: Block,
                  node_map: dict, positions: dict,
                  lora: LoRaChannel, fanout: int = GOSSIP_FANOUT) -> set:
        seen    = {origin_id}
        queue   = deque([origin_id])
        reached = {origin_id}

        while queue:
            cur_id   = queue.popleft()
            cur_node = node_map.get(cur_id)
            if cur_node is None:
                continue

            candidates = [p for p in cur_node.peers if p.node_id not in seen]
            targets    = candidates[:fanout]

            for peer in targets:
                seen.add(peer.node_id)
                delivered = lora.deliver(positions[cur_id], positions[peer.node_id])

                self._bus.post({"type": "gossip_hop",
                                "src": cur_id,
                                "dst": peer.node_id,
                                "dropped": not delivered})
                self._bus.sleep(0.06)

                if not delivered:
                    continue

                chain = peer.chain
                if chain.tip_hash() == block.block_hash:
                    reached.add(peer.node_id)
                    queue.append(peer.node_id)
                    continue
                if chain.tip_hash() == block.prev_hash:
                    chain.append(block)
                    reached.add(peer.node_id)
                    queue.append(peer.node_id)

        return reached
