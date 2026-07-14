"""
Change point detection and pattern matching for NILM.
"""

import logging

import numpy as np


logger = logging.getLogger(__name__)


class ChangePointPatternDetector:
    """
    Hybrid detector combining change point detection and pattern matching.

    Approach:
    1. Detect change points (significant jumps) in the aggregate
    2. Extract patterns between baselines
    3. Compare against known signature profiles
    4. Reconstruct complete cycles
    """

    def __init__(self, min_power_change=500, min_duration=300):
        """
        Args:
            min_power_change: Minimum threshold to detect a change point (W)
            min_duration: Minimum duration of a pattern (seconds)
        """
        self.min_power_change = min_power_change
        self.min_duration = min_duration
        self.signature_profiles = {}  # {appliance_id: [profiles]}

    def add_signature_profile(
        self,
        appliance_id,
        appliance_name,
        power_sequence,
        duration,
        signature_id=None,
        morphology=None,
    ):
        """
        Add a signature profile with morphological analysis.

        Args:
            appliance_id: Appliance ID
            appliance_name: Appliance name
            power_sequence: Power sequence
            duration: Duration in seconds
            signature_id: Signature ID (optional)
            morphology: Morphological analysis (optional)
        """
        if appliance_id not in self.signature_profiles:
            self.signature_profiles[appliance_id] = {
                "name": appliance_name,
                "profiles": [],
            }

        # Normalize the profile (0-1)
        if len(power_sequence) > 0:
            profile_max = np.max(power_sequence)
            if profile_max > 0:
                normalized = power_sequence / profile_max

                profile = {
                    "signature_id": signature_id,
                    "pattern": normalized,
                    "duration": duration,  # seconds
                    "avg_power": float(np.mean(power_sequence)),
                    "max_power": float(profile_max),
                    # energy_wh from signature: avg_power * duration(s) / 3600
                    "energy_wh": float(np.mean(power_sequence)) * duration / 3600.0,
                }

                # Add morphological features if available
                if morphology:
                    profile["morphology"] = morphology

                self.signature_profiles[appliance_id]["profiles"].append(profile)

    def detect_change_points(self, aggregate_power):
        """
        Detect change points in the aggregate consumption.

        Uses an algorithm based on gradient and local variance.

        Args:
            aggregate_power: Aggregate consumption

        Returns:
            List of change points with indices and amplitudes
        """
        if len(aggregate_power) < 10:
            return []

        # Compute the gradient (discrete derivative)
        gradient = np.diff(aggregate_power)

        # Smooth to reduce noise (5-point moving average)
        window_size = 5
        if len(gradient) >= window_size:
            gradient_smooth = np.convolve(gradient, np.ones(window_size) / window_size, mode="valid")
        else:
            gradient_smooth = gradient

        # Detect significant jumps
        change_points = []
        threshold = self.min_power_change

        i = 0
        while i < len(gradient_smooth):
            # Look for a significant jump
            if abs(gradient_smooth[i]) > threshold / 10:  # Sensitive initial detection
                # Check if it's a real jump (sum over the window)
                window_end = min(i + 30, len(gradient_smooth))  # 30s window
                cumsum = np.sum(gradient_smooth[i:window_end])

                if abs(cumsum) > threshold:
                    # Change point detected
                    change_points.append(
                        {
                            "index": i + window_size // 2,
                            "amplitude": float(cumsum),
                            "direction": "up" if cumsum > 0 else "down",
                        }
                    )  # Adjust for the smoothing
                    # Skip the window to avoid duplicates
                    i = window_end
                    continue
            i += 1

        logger.info(f"Change points detected: {len(change_points)}")
        return change_points

    def extract_patterns(self, aggregate_power, change_points, timestamps=None):
        """
        Extract patterns between change points.

        Args:
            aggregate_power: Aggregate consumption
            change_points: Detected change points
            timestamps: List of timestamps matching aggregate_power (optional)
                        When given, duration is computed in real seconds.
                        When absent, estimated from the sampling rate.

        Returns:
            List of patterns with sequences and metadata
        """
        from ..morphology import MorphologyAnalyzer

        if len(change_points) < 2:
            return []

        # Estimate the sampling interval (seconds/sample)
        if timestamps and len(timestamps) > 1:
            total_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
            sample_interval = total_seconds / max(len(timestamps) - 1, 1)
        else:
            # Fallback: assume 8s/sample (typical for HA Linky)
            sample_interval = 8.0

        # min_duration is in seconds -> convert to samples for the initial filter
        min_duration_samples = max(1, int(self.min_duration / sample_interval))

        patterns = []
        analyzer = MorphologyAnalyzer()

        # Group change points into segments
        i = 0
        while i < len(change_points):
            cp = change_points[i]

            if cp["direction"] == "up":
                # Look for the matching DOWN change point
                end_idx = None
                for j in range(i + 1, len(change_points)):
                    if change_points[j]["direction"] == "down":
                        end_idx = j
                        break

                if end_idx is not None:
                    start = cp["index"]
                    end = change_points[end_idx]["index"]
                    duration_samples = end - start

                    # Duration in real seconds (fixes the unit bug)
                    if timestamps and start < len(timestamps) and end < len(timestamps):
                        duration_seconds = (timestamps[end] - timestamps[start]).total_seconds()
                    else:
                        duration_seconds = duration_samples * sample_interval

                    if duration_samples >= min_duration_samples:
                        pattern = aggregate_power[start:end]

                        if len(pattern) > 0 and np.max(pattern) > self.min_power_change:
                            try:
                                morphology = analyzer.analyze(pattern.tolist(), start_time=None)
                            except Exception as e:
                                logger.warning(f"Error computing pattern morphology: {e}")
                                morphology = None

                            # Correct energy: avg_power × real_duration / 3600
                            energy_wh = float(np.mean(pattern)) * duration_seconds / 3600.0

                            patterns.append(
                                {
                                    "start_idx": start,
                                    "end_idx": end,
                                    "duration": duration_seconds,   # seconds (fixed)
                                    "duration_samples": duration_samples,
                                    "pattern": pattern,
                                    "avg_power": float(np.mean(pattern)),
                                    "max_power": float(np.max(pattern)),
                                    "energy_wh": energy_wh,
                                    "morphology": morphology,
                                }
                            )

                    i = end_idx + 1
                else:
                    i += 1
            else:
                i += 1

        logger.info(f"Patterns extracted: {len(patterns)} (interval ~{sample_interval:.1f}s/pt)")
        return patterns

    def match_pattern(self, pattern_data, pattern_morphology=None):
        """
        Compare a pattern against known signature profiles.
        Uses morphological features if available for better matching.

        Args:
            pattern_data: Pattern data to match
            pattern_morphology: Morphological analysis of the pattern (optional)

        Returns:
            (appliance_id, appliance_name, signature_id, confidence) or None
        """
        if not self.signature_profiles:
            return None

        pattern = pattern_data["pattern"]
        pattern_duration = pattern_data["duration"]    # seconds (fixed)
        pattern_power = pattern_data["avg_power"]
        pattern_energy = pattern_data.get("energy_wh", 0.0)

        # Normalize the pattern (0-1)
        pattern_max = np.max(pattern)
        if pattern_max == 0:
            return None
        pattern_normalized = pattern / pattern_max

        best_match = None
        best_score = 0.0

        for appliance_id, data in self.signature_profiles.items():
            appliance_name = data["name"]
            logger.info(
                f"Comparing pattern ({pattern_duration:.0f}s, {pattern_power:.0f}W, "
                f"{pattern_energy:.2f}Wh) against {len(data['profiles'])} profiles of {appliance_name}"
            )

            for i, profile in enumerate(data["profiles"]):
                # --- Duration filter: ±75% (wide, to handle variable washer/heater cycles) ---
                if profile["duration"] <= 0:
                    continue
                duration_ratio = pattern_duration / profile["duration"]
                if duration_ratio < 0.25 or duration_ratio > 4.0:
                    continue

                # --- Power filter: ±40% ---
                if profile["avg_power"] <= 0:
                    continue
                power_ratio = pattern_power / profile["avg_power"]
                if power_ratio < 0.60 or power_ratio > 1.40:
                    continue

                # --- Duration and power scores ---
                duration_score = max(0.0, 1.0 - abs(1.0 - duration_ratio) / 2.0)
                power_score = max(0.0, 1.0 - abs(1.0 - power_ratio))

                # --- Energy score (more stable than power alone) ---
                profile_energy = profile.get("energy_wh", 0.0)
                if profile_energy > 0 and pattern_energy > 0:
                    energy_ratio = pattern_energy / profile_energy
                    energy_score = max(0.0, 1.0 - abs(1.0 - energy_ratio) / 2.0)
                else:
                    energy_score = 0.5  # neutral if no energy data

                # --- Shape correlation ---
                target_len = min(len(pattern_normalized), len(profile["pattern"]))
                if target_len < 5:
                    continue

                pattern_resampled = np.interp(
                    np.linspace(0, len(pattern_normalized) - 1, target_len),
                    np.arange(len(pattern_normalized)),
                    pattern_normalized,
                )
                profile_resampled = np.interp(
                    np.linspace(0, len(profile["pattern"]) - 1, target_len),
                    np.arange(len(profile["pattern"])),
                    profile["pattern"],
                )

                corr_mat = np.corrcoef(pattern_resampled, profile_resampled)
                abs_correlation = abs(corr_mat[0, 1]) if not np.isnan(corr_mat[0, 1]) else 0.0

                # --- Morphology score if available ---
                morphology_score = 0.0
                has_morphology = pattern_morphology and "morphology" in profile
                if has_morphology:
                    morphology_score = self._compute_morphology_similarity(
                        pattern_morphology, profile["morphology"]
                    )

                # --- Combined score ---
                # Energy = the most stable feature across appliance types
                # Duration = strong constraint (wide bounds in the filter)
                # Power = secondary constraint
                # Shape = bonus (noisy on real-world data)
                # Morphology = bonus when available
                if has_morphology:
                    combined_score = (
                        energy_score * 0.35
                        + duration_score * 0.25
                        + power_score * 0.20
                        + abs_correlation * 0.10
                        + morphology_score * 0.10
                    )
                else:
                    combined_score = (
                        energy_score * 0.40
                        + duration_score * 0.30
                        + power_score * 0.20
                        + abs_correlation * 0.10
                    )

                logger.info(
                    f"  Profile#{i}: energy={energy_score:.3f}, dur={duration_score:.3f}, "
                    f"pow={power_score:.3f}, corr={abs_correlation:.3f}, "
                    f"morpho={morphology_score:.3f} -> combined={combined_score:.3f}"
                )

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = (
                        appliance_id,
                        appliance_name,
                        profile.get("signature_id"),
                        combined_score,
                    )

        # Low threshold: better a false positive than a false negative (the user validates)
        threshold = 0.25

        logger.info(f"Matching done: best_score={best_score:.3f}, threshold={threshold}")

        if best_match and best_match[3] > threshold:
            logger.info(
                f"Match found: {best_match[1]} "
                f"(sig_id={best_match[2]}, confidence={best_match[3]:.3f})"
            )
            return best_match
        else:
            logger.info(f"No match (best={best_score:.3f} < {threshold})")
            return None

    def _compute_morphology_similarity(self, morpho1, morpho2):
        """
        Compute similarity between two morphological analyses.

        Args:
            morpho1: First morphological analysis
            morpho2: Second morphological analysis

        Returns:
            Similarity score [0-1]
        """
        score = 0.0
        weight_sum = 0.0

        # 1. Pattern type match (weight: 0.3)
        if "shape_features" in morpho1 and "shape_features" in morpho2:
            type1 = morpho1["shape_features"].get("pattern_type", "")
            type2 = morpho2["shape_features"].get("pattern_type", "")
            if type1 == type2:
                score += 0.3
            weight_sum += 0.3

        # 2. Oscillation features (weight: 0.25)
        if "oscillation_features" in morpho1 and "oscillation_features" in morpho2:
            osc1 = morpho1["oscillation_features"]
            osc2 = morpho2["oscillation_features"]

            # Both oscillate or both don't
            if osc1.get("is_oscillating") == osc2.get("is_oscillating"):
                osc_score = 0.25

                # If both oscillate, compare frequency
                if osc1.get("is_oscillating"):
                    freq1 = osc1.get("oscillation_frequency_hz", 0)
                    freq2 = osc2.get("oscillation_frequency_hz", 0)
                    if freq2 > 0:
                        freq_ratio = min(freq1, freq2) / max(freq1, freq2)
                        osc_score *= freq_ratio

                score += osc_score
            weight_sum += 0.25

        # 3. Gradient features (weight: 0.2)
        if "gradient" in morpho1 and "gradient" in morpho2:
            grad1 = morpho1["gradient"]
            grad2 = morpho2["gradient"]

            # Compare max rise rate
            rise1 = grad1.get("max_rise_rate", 0)
            rise2 = grad2.get("max_rise_rate", 0)
            if max(rise1, rise2) > 0:
                rise_sim = min(rise1, rise2) / max(rise1, rise2)
                score += rise_sim * 0.1

            # Compare max fall rate
            fall1 = abs(grad1.get("max_fall_rate", 0))
            fall2 = abs(grad2.get("max_fall_rate", 0))
            if max(fall1, fall2) > 0:
                fall_sim = min(fall1, fall2) / max(fall1, fall2)
                score += fall_sim * 0.1

            weight_sum += 0.2

        # 4. Plateaus similarity (weight: 0.15)
        if "plateaus" in morpho1 and "plateaus" in morpho2:
            plat1 = morpho1["plateaus"]
            plat2 = morpho2["plateaus"]

            # Compare number of plateaus
            num1 = len(plat1) if plat1 else 0
            num2 = len(plat2) if plat2 else 0

            if max(num1, num2) > 0:
                num_sim = min(num1, num2) / max(num1, num2)
                score += num_sim * 0.15
            else:
                # Both have no plateaus = similar
                score += 0.15

            weight_sum += 0.15

        # 5. Statistical moments (weight: 0.1)
        if "statistical_moments" in morpho1 and "statistical_moments" in morpho2:
            stat1 = morpho1["statistical_moments"]
            stat2 = morpho2["statistical_moments"]

            # Compare skewness (sign of asymmetry)
            skew1 = stat1.get("skewness", 0)
            skew2 = stat2.get("skewness", 0)

            # Same skew sign = good
            if (skew1 * skew2) >= 0:
                score += 0.1

            weight_sum += 0.1

        # Normalize by the total weight
        if weight_sum > 0:
            return score / weight_sum
        else:
            return 0.0
