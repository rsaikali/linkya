"""
Appliance state detection using clustering.
"""

import logging

import numpy as np
from sklearn.cluster import KMeans


logger = logging.getLogger(__name__)


class ApplianceStateDetector:
    """State/cycle detector for an appliance"""

    def __init__(self, n_states=5):
        """
        Args:
            n_states: Number of states to detect (default 5: off, low, medium, high, peak)
        """
        self.n_states = n_states
        self.kmeans = None
        self.state_thresholds = None

    def fit(self, power_values):
        """
        Train the state detector on consumption data

        Args:
            power_values: Array of power values

        Returns:
            Self for chaining
        """
        if len(power_values) < self.n_states:
            logger.warning(f"Not enough data for {self.n_states} states, reducing automatically")
            self.n_states = max(2, len(power_values) // 10)

        # Reshape for KMeans
        power_reshaped = power_values.reshape(-1, 1)

        # Clustering to identify states
        self.kmeans = KMeans(n_clusters=self.n_states, random_state=42, n_init=10)
        self.kmeans.fit(power_reshaped)

        # Compute thresholds between states (sorted centers)
        centers = sorted(self.kmeans.cluster_centers_.flatten())
        self.state_thresholds = centers

        logger.info(f"States detected: {len(centers)} levels = {[f'{c:.1f}W' for c in centers]}")
        return self

    def predict_states(self, power_values):
        """
        Predict states for a consumption sequence

        Args:
            power_values: Array of power values

        Returns:
            Tuple (predicted states, detected cycles)
        """
        if self.kmeans is None:
            raise ValueError("The detector must be trained before prediction (fit)")

        # Predict states
        power_reshaped = power_values.reshape(-1, 1)
        states = self.kmeans.predict(power_reshaped)

        # Detect cycles (state transitions)
        cycles = self._detect_cycles(states, power_values)

        return states, cycles

    def _detect_cycles(self, states, power_values):
        """
        Detect cycles/phases in state transitions

        Args:
            states: Array of predicted states
            power_values: Corresponding power values

        Returns:
            List of detected cycles with metadata
        """
        cycles = []
        current_state = states[0]
        start_idx = 0

        for i in range(1, len(states)):
            # State transition detected
            if states[i] != current_state:
                # Record the previous cycle
                if i - start_idx >= 10:  # Minimum 10 points (10 seconds)
                    cycle_power = power_values[start_idx:i]
                    cycles.append(
                        {
                            "state": int(current_state),
                            "start_idx": int(start_idx),
                            "end_idx": int(i),
                            "duration_seconds": int(i - start_idx),
                            "avg_power": float(np.mean(cycle_power)),
                            "max_power": float(np.max(cycle_power)),
                            "energy_wh": float(np.sum(cycle_power) / 3600),  # Wh (1Hz = 1s)
                        }
                    )

                # New cycle
                current_state = states[i]
                start_idx = i

        # Last cycle
        if len(states) - start_idx >= 10:
            cycle_power = power_values[start_idx:]
            cycles.append(
                {
                    "state": int(current_state),
                    "start_idx": int(start_idx),
                    "end_idx": int(len(states)),
                    "duration_seconds": int(len(states) - start_idx),
                    "avg_power": float(np.mean(cycle_power)),
                    "max_power": float(np.max(cycle_power)),
                    "energy_wh": float(np.sum(cycle_power) / 3600),
                }
            )

        return cycles
