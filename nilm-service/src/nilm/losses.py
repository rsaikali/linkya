"""
Custom loss functions for NILM training.
"""

import tensorflow as tf


@tf.keras.utils.register_keras_serializable(package="custom_losses")
def focal_loss_fixed(y_true=None, y_pred=None, gamma=2.0, alpha=0.25):
    """
    Focal Loss to focus on hard examples.

    Reduces the loss for well-classified examples and increases it
    for hard ones. Useful for rejecting false positives.

    Args:
        y_true: Ground-truth values (None if used as a constructor)
        y_pred: Predicted values (None if used as a constructor)
        gamma: Modulation factor (2.0 default).
               Higher = more focus on hard examples
        alpha: Balance factor (0.25 default).
               Relative weight of classes

    Returns:
        Computed loss if y_true and y_pred are given, otherwise a loss function
    """
    # If y_true and y_pred are given, compute the loss directly
    if y_true is not None and y_pred is not None:
        # Base MAE
        mae = tf.abs(y_true - y_pred)

        # Normalize errors for the focal term
        # For predictions close to ground truth, p_t will be close to 1
        # For large errors, p_t will be close to 0
        max_error = tf.reduce_max(mae) + 1e-7
        p_t = 1.0 - (mae / max_error)

        # Focal term: (1 - p_t)^gamma
        # When p_t is close to 1 (good prediction): focal_weight ~0
        # When p_t is close to 0 (bad prediction): focal_weight ~1
        focal_weight = tf.pow(1.0 - p_t, gamma)

        # Penalize false positives more heavily (y_true=0 but y_pred>0)
        false_positive_mask = tf.cast(y_true < 0.1, tf.float32)
        alpha_weight = 1.0 + alpha * false_positive_mask

        # Final loss
        loss = alpha_weight * focal_weight * mae

        return tf.reduce_mean(loss)

    # Otherwise return a parameterized loss function
    def loss_fn(y_true, y_pred):
        # Base MAE
        mae = tf.abs(y_true - y_pred)

        # Normalize errors for the focal term
        # For predictions close to ground truth, p_t will be close to 1
        # For large errors, p_t will be close to 0
        max_error = tf.reduce_max(mae) + 1e-7
        p_t = 1.0 - (mae / max_error)

        # Focal term: (1 - p_t)^gamma
        # When p_t is close to 1 (good prediction): focal_weight ~0
        # When p_t is close to 0 (bad prediction): focal_weight ~1
        focal_weight = tf.pow(1.0 - p_t, gamma)

        # Penalize false positives more heavily (y_true=0 but y_pred>0)
        false_positive_mask = tf.cast(y_true < 0.1, tf.float32)
        alpha_weight = 1.0 + alpha * false_positive_mask

        # Final loss
        loss = alpha_weight * focal_weight * mae

        return tf.reduce_mean(loss)

    return loss_fn


@tf.keras.utils.register_keras_serializable(package="custom_losses")
def asymmetric_loss(y_true=None, y_pred=None, false_positive_penalty=1.5):
    """
    Asymmetric loss that penalizes false positives more heavily.

    When y_true=0 (appliance off or negative signature), prediction
    errors are penalized more.

    Args:
        y_true: Ground-truth values (None if used as a constructor)
        y_pred: Predicted values (None if used as a constructor)
        false_positive_penalty: Multiplier for false positives
                                (default: 1.5, down from 2.5 to be less aggressive)

    Returns:
        Computed loss if y_true and y_pred are given, otherwise a loss function
    """
    # If y_true and y_pred are given, compute the loss directly
    if y_true is not None and y_pred is not None:
        mae = tf.abs(y_true - y_pred)

        # Detect where y_true is close to 0 (OFF or negative)
        is_negative = tf.cast(y_true < 0.1, tf.float32)

        # Penalize errors more when the appliance should be OFF
        weight = 1.0 + (false_positive_penalty - 1.0) * is_negative

        weighted_mae = weight * mae

        return tf.reduce_mean(weighted_mae)

    # Otherwise return a parameterized loss function
    def loss_fn(y_true, y_pred):
        mae = tf.abs(y_true - y_pred)

        # Detect where y_true is close to 0 (OFF or negative)
        is_negative = tf.cast(y_true < 0.1, tf.float32)

        # Penalize errors more when the appliance should be OFF
        weight = 1.0 + (false_positive_penalty - 1.0) * is_negative

        weighted_mae = weight * mae

        return tf.reduce_mean(weighted_mae)

    return loss_fn
