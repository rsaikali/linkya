"""
Utility functions for NILM processing.
"""

import re


def normalize_name_for_tensorflow(name):
    """
    Normalize a name to be TensorFlow/Keras-compatible.
    TensorFlow scope names must match the pattern: ^[A-Za-z0-9.][A-Za-z0-9_.\\/>-]*$

    Args:
        name: Name to normalize

    Returns:
        Normalized name (spaces -> underscores, special characters stripped)
    """
    # Replace spaces with underscores
    normalized = name.replace(" ", "_")
    # Strip apostrophes
    normalized = normalized.replace("'", "")
    # Keep only alphanumeric characters, dots, underscores, slashes, dashes
    normalized = re.sub(r"[^A-Za-z0-9._/\->]", "", normalized)
    # Ensure the name starts with a letter, digit, or dot
    if normalized and not re.match(r"^[A-Za-z0-9.]", normalized):
        normalized = "appliance_" + normalized
    return normalized if normalized else "unknown_appliance"
