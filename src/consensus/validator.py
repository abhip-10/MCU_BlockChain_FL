from src.blockchain.block import Block
from src.blockchain.chain import Chain

ANOMALY_THRESHOLD = 0.7


def validate(block: Block, chain: Chain) -> tuple[bool, str]:
    """
    Run the 5-check PoA validation pipeline.
    Returns (passed, reason). reason is 'ok' on success.
    """
    pub = chain.public_keys.get(block.node_id)
    if not pub or not block.verify_signature(pub):
        return False, "invalid_signature"

    if block.compute_hash() != block.block_hash:
        return False, "invalid_hash"

    if block.prev_hash != chain.tip_hash():
        return False, "invalid_prev_hash"

    if block.frame_counter <= chain.last_frame_counter(block.node_id):
        return False, "replay_or_counter_manipulation"

    if block.anomaly_score > ANOMALY_THRESHOLD:
        return False, "anomaly_score_too_high"

    return True, "ok"
