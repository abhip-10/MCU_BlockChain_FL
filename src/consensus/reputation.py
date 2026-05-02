class ReputationEngine:
    """
    Score per node in [0.0, 1.0], initial 0.5.
    Reward on valid block approved; penalize on rejection.
    vote_weight() scales a validator's influence in PoA threshold.
    Flagged when score drops below 0.2 (after ~3 consecutive rejections).
    """

    INITIAL = 0.5
    REWARD  = 0.05
    PENALTY = 0.15
    FLAG_THRESHOLD = 0.2

    def __init__(self) -> None:
        self._scores: dict[str, float] = {}

    def _score(self, node_id: str) -> float:
        return self._scores.setdefault(node_id, self.INITIAL)

    def reward(self, node_id: str) -> None:
        self._scores[node_id] = min(1.0, self._score(node_id) + self.REWARD)

    def penalize(self, node_id: str) -> None:
        self._scores[node_id] = max(0.0, self._score(node_id) - self.PENALTY)

    def vote_weight(self, node_id: str) -> float:
        return self._score(node_id)

    def is_flagged(self, node_id: str) -> bool:
        return self._score(node_id) < self.FLAG_THRESHOLD

    def score(self, node_id: str) -> float:
        return self._score(node_id)

    def all_scores(self) -> dict[str, float]:
        return dict(self._scores)
