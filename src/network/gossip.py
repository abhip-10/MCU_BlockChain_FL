"""
Gossip protocol: flood a committed block through the partial mesh.
Each hop is gated by the LoRa channel's stochastic PDR.
Nodes that already hold the block are skipped (seen-set deduplication).
"""
from collections import deque

from src.blockchain.block import Block
from src.network.lora_sim import LoRaChannel

FANOUT = 3


class GossipProtocol:
    def broadcast(
        self,
        origin_id: str,
        block: Block,
        node_map: dict,          # node_id -> VirtualNode
        positions: dict,         # node_id -> (x_m, y_m)
        lora: LoRaChannel,
        fanout: int = FANOUT,
    ) -> set:
        """
        Flood block from origin through mesh neighbours.
        Returns the set of node_ids that received the block.
        """
        seen    = {origin_id}
        queue   = deque([origin_id])
        reached = {origin_id}

        while queue:
            cur_id   = queue.popleft()
            cur_node = node_map[cur_id]

            candidates = [p for p in cur_node.peers if p.node_id not in seen]
            targets    = candidates[:fanout]

            for peer in targets:
                seen.add(peer.node_id)

                if not lora.deliver(positions[cur_id], positions[peer.node_id]):
                    continue

                chain = peer.chain
                # already holds this block
                if chain.tip_hash() == block.block_hash:
                    reached.add(peer.node_id)
                    queue.append(peer.node_id)
                    continue

                # chain is ready to accept this block
                if chain.tip_hash() == block.prev_hash:
                    chain.append(block)
                    reached.add(peer.node_id)
                    queue.append(peer.node_id)
                # else: node is behind by more than one block — needs full sync

        return reached
