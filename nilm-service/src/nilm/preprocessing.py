"""
Data preprocessing for Sequence-to-Point NILM models.
"""

import logging

import numpy as np
from sklearn.preprocessing import MinMaxScaler, StandardScaler


logger = logging.getLogger(__name__)


class Seq2PointPreprocessor:
    """Preprocessing for the Sequence-to-Point model"""

    def __init__(self, sequence_length=599):
        """
        Args:
            sequence_length: Input window length (odd, for a center point)
        """
        # Force odd length to have a center point
        self.sequence_length = sequence_length if sequence_length % 2 == 1 else sequence_length - 1
        self.input_scaler = StandardScaler()
        self.target_scaler = MinMaxScaler(feature_range=(0, 1))
        self.fitted = False

    def create_sequences(self, aggregate_power, appliance_power, stride=1):
        """
        Create sequences for Sequence-to-Point training

        Args:
            aggregate_power: Total (aggregate) consumption
            appliance_power: Target appliance consumption
            stride: Window step size

        Returns:
            Tuple (X: input sequences, y: target values at the center point)
        """
        if len(aggregate_power) != len(appliance_power):
            raise ValueError("aggregate_power and appliance_power must have the same length")

        if len(aggregate_power) < self.sequence_length:
            logger.warning(f"Sequence too short ({len(aggregate_power)} < {self.sequence_length})")
            return np.array([]), np.array([])

        X, y = [], []
        half_window = self.sequence_length // 2

        for i in range(half_window, len(aggregate_power) - half_window, stride):
            # Input window centered on i
            window = aggregate_power[i - half_window : i + half_window + 1]

            # Target: appliance consumption at the center point
            target = appliance_power[i]

            X.append(window)
            y.append(target)

        X = np.array(X, dtype=np.float32)
        y = np.array(y, dtype=np.float32)

        return X, y

    def create_prediction_windows(self, aggregate_power, stride=1):
        """
        Creates sliding windows for prediction (inference mode).

        Args:
            aggregate_power: Aggregate consumption data
            stride: Window step size

        Returns:
            Array of windows for prediction
        """
        if len(aggregate_power) < self.sequence_length:
            logger.warning(f"Sequence too short ({len(aggregate_power)} < {self.sequence_length})")
            return np.array([])

        X = []
        half_window = self.sequence_length // 2

        for i in range(half_window, len(aggregate_power) - half_window, stride):
            window = aggregate_power[i - half_window : i + half_window + 1]
            X.append(window)

        return np.array(X, dtype=np.float32)

    def fit(self, aggregate_power, appliance_power):
        """
        Fit the scalers on the training data

        Args:
            aggregate_power: Total consumption
            appliance_power: Appliance consumption
        """
        # Fit scaler for the input (aggregate)
        self.input_scaler.fit(aggregate_power.reshape(-1, 1))

        # Fit scaler for the target (appliance)
        self.target_scaler.fit(appliance_power.reshape(-1, 1))

        self.fitted = True
        logger.info(
            f"Scalers fitted: input=[{aggregate_power.min():.1f}, {aggregate_power.max():.1f}], "
            f"target=[{appliance_power.min():.1f}, {appliance_power.max():.1f}]"
        )

    def transform(self, X, y=None):
        """
        Transform the data with the scalers

        Args:
            X: Input sequences
            y: Target values (optional)

        Returns:
            Tuple (transformed X, transformed y or None)
        """
        if not self.fitted:
            raise ValueError("The preprocessor must be fitted before transform")

        # Normalize X (each sequence independently)
        X_scaled = np.zeros_like(X)
        for i in range(len(X)):
            X_scaled[i] = self.input_scaler.transform(X[i].reshape(-1, 1)).flatten()

        # Normalize y if provided
        y_scaled = None
        if y is not None:
            y_scaled = self.target_scaler.transform(y.reshape(-1, 1)).flatten()

        return X_scaled, y_scaled

    def inverse_transform_target(self, y_scaled):
        """
        Invert the transformation for predictions

        Args:
            y_scaled: Normalized values

        Returns:
            Original values
        """
        return self.target_scaler.inverse_transform(y_scaled.reshape(-1, 1)).flatten()
