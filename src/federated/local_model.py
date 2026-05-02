import hashlib

import numpy as np


class LocalModel:
    """
    Simulates a tiny on-device neural network as a float-weight vector.
    In firmware this maps to an Edge Impulse exported model's weight array.
    """

    def __init__(self, initial_weights: np.ndarray) -> None:
        self.weights = initial_weights.copy().astype(np.float64)

    def train(self, learning_rate: float = 0.01) -> np.ndarray:
        """Simulate one local training step. Returns the weight delta."""
        delta = np.random.randn(len(self.weights))
        self.weights += learning_rate * delta
        return delta

    def serialize(self) -> bytes:
        return self.weights.tobytes()

    def weight_hash(self) -> str:
        return hashlib.sha256(self.serialize()).hexdigest()

    def convergence_delta(self, other: "LocalModel") -> float:
        """L2 distance between this model and another — tracks convergence."""
        return float(np.linalg.norm(self.weights - other.weights))
