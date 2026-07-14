"""
Sequence-to-Point NILM model for disaggregating concurrent appliances
and detecting complex cycles.

LSTM/GRU-based architecture with an attention mechanism for:
- Disaggregation: predicts each appliance's individual consumption
- State detection: identifies the different phases/cycles (heating, washing, etc.)
- Concurrent appliances: handles several appliances running simultaneously
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np
from sqlalchemy import text

from .config import settings
from .database import db_manager
from .nilm.detectors import ChangePointPatternDetector
from .nilm.models import Seq2PointMultiOutputModel


logger = logging.getLogger(__name__)


class Seq2PointNILMManager:
    """Manager for S2P NILM models with a Multi-Output architecture"""

    def __init__(self):
        self.model_type = os.getenv("NILM_MODEL_TYPE", "gru").lower()
        # Architecture: 'multioutput'
        self.architecture = os.getenv("NILM_ARCHITECTURE", "multioutput").lower()

        # Create the models directory
        Path(settings.nilm_model_path).mkdir(parents=True, exist_ok=True)

        # Hybrid change point + pattern matching detector
        self.change_point_detector = ChangePointPatternDetector(
            min_power_change=settings.nilm_min_power_threshold, min_duration=settings.nilm_min_duration_seconds
        )
        logger.info("Change Point Pattern Detector initialized")

        # Multi-Output model
        self.multioutput_model = None

        logger.info(f"Architecture: {self.architecture.upper()}, " f"Type: {self.model_type.upper()}")

    def load_model(self, model_path):
        """
        Load an existing model for fine-tuning.

        Args:
            model_path: Path to the .keras model to load
        """
        try:
            # Load the metadata
            metadata_path = Path(model_path).with_suffix(".metadata.json")
            if not metadata_path.exists():
                raise ValueError(f"Metadata not found: {metadata_path}")

            with open(metadata_path, "r") as f:
                metadata = json.load(f)

            appliance_ids = metadata.get("appliance_ids", [])
            appliance_names = metadata.get("appliance_names", [])
            sequence_length = metadata.get("sequence_length", settings.effective_sequence_length)
            architecture = metadata.get("architecture", "MultiOutput")

            logger.info(f"Loading model {architecture}...")

            if architecture.lower() == "multioutput":
                self.multioutput_model = Seq2PointMultiOutputModel(
                    appliance_ids=appliance_ids, appliance_names=appliance_names, sequence_length=sequence_length, model_type=self.model_type
                )
                self.multioutput_model.load(model_path)
                self.architecture = "multioutput"
            else:
                raise ValueError(f"Architecture {architecture} not supported. " f"Only 'MultiOutput' is available.")

            logger.info(f"Model {architecture} loaded: {model_path}")

        except Exception as e:
            logger.error(f"Error loading model: {e}")
            raise

    def train_all_appliances(self, model_name, fine_tune=False):
        """
        Train the model on all appliances (Multi-Output).

        Args:
            model_name: Name of the model (format: linkya_model_<timestamp>)
            fine_tune: If True, continue training the existing model

        Returns:
            Global dict of metrics
        """
        try:
            with db_manager.get_session() as session:
                query = """
                    SELECT DISTINCT a.id, a.name, COUNT(s.id) as num_signatures
                    FROM nilm_appliances a
                    JOIN nilm_signatures s ON s.appliance_id = a.id
                    GROUP BY a.id, a.name
                    HAVING COUNT(s.id) >= 2
                    ORDER BY a.name
                """
                appliances = session.execute(text(query)).fetchall()

            if len(appliances) < 1:
                logger.error("No appliance with enough signatures (minimum 2)")
                return {"error": "insufficient_data", "min_appliances": 1}

            appliance_ids = [row[0] for row in appliances]
            appliance_names = [row[1] for row in appliances]

            # Load signatures
            all_signatures = {}
            with db_manager.get_session() as session:
                for appliance_id in appliance_ids:
                    query = """
                        SELECT id, appliance_id, start_time, end_time
                        FROM nilm_signatures
                        WHERE appliance_id = :appliance_id
                        ORDER BY created_at
                    """
                    result = session.execute(text(query), {"appliance_id": appliance_id})
                    all_signatures[appliance_id] = [dict(row._mapping) for row in result]

            # Load profiles for the change point detector
            logger.info("Loading signature profiles...")
            for appliance_id, signatures in all_signatures.items():
                app_idx = appliance_ids.index(appliance_id)
                appliance_name = appliance_names[app_idx]
                for sig in signatures:
                    # Load signature data
                    agg, app_pwr = Seq2PointMultiOutputModel._load_signature_data_static(sig)
                    if app_pwr is None or len(app_pwr) == 0:
                        continue

                    duration = int((sig["end_time"] - sig["start_time"]).total_seconds())

                    self.change_point_detector.add_signature_profile(
                        appliance_id=appliance_id, appliance_name=appliance_name, power_sequence=app_pwr, duration=duration, signature_id=sig["id"]
                    )

            total_profiles = sum(len(data["profiles"]) for data in (self.change_point_detector.signature_profiles.values()))
            logger.info(f"{len(self.change_point_detector.signature_profiles)} " f"appliances, {total_profiles} profiles")

            # Train with the chosen architecture
            if self.architecture == "multioutput":
                logger.info("Multi-Output training " "(parallel outputs + attention)")

                # Create or reuse the Multi-Output model
                if fine_tune and self.multioutput_model is not None:
                    logger.info("Reusing Multi-Output model " "for fine-tuning")
                else:
                    self.multioutput_model = Seq2PointMultiOutputModel(
                        appliance_ids, appliance_names, sequence_length=settings.effective_sequence_length, model_type=self.model_type
                    )

                metrics = self.multioutput_model.train(all_signatures, model_name, epochs=30, batch_size=32, use_feedback=True, fine_tune=fine_tune)

                if not metrics:
                    logger.error("Multi-Output training impossible " "(insufficient data)")
                    return {"error": "insufficient_training_data"}

                model_path = Path(settings.nilm_model_path) / (f"{model_name}.keras")
                self.multioutput_model.save(str(model_path), metadata=metrics)
                architecture_name = "MultiOutput"

            # Format the response for frontend compatibility
            return {
                "model_name": model_name,
                "model_type": f"{architecture_name}-{self.model_type}",
                "architecture": architecture_name,
                "num_appliances": len(appliance_ids),
                "model_path": str(model_path),
                "appliances": [
                    {
                        "id": appliance_ids[i],
                        "name": appliance_names[i],
                        "num_signatures": len(all_signatures[appliance_ids[i]]),
                        "metrics": {
                            "train_mae": metrics.get(f"{appliance_names[i]}_train_mae"),
                            "val_mae": metrics.get(f"{appliance_names[i]}_val_mae"),
                            "train_loss": metrics.get(f"{appliance_names[i]}_train_loss", metrics.get("train_loss")),
                            "val_loss": metrics.get(f"{appliance_names[i]}_val_loss", metrics.get("val_loss")),
                            "epochs_trained": metrics.get("epochs_trained"),
                        },
                    }
                    for i in range(len(appliance_ids))
                ],
            }

        except Exception as e:
            logger.error(f"Global training error: {e}", exc_info=True)
            return {"error": str(e)}

    def _filter_against_negative_signatures(self, detections):
        """
        Filter out detections that look like negative signatures.

        A negative signature is created when the user invalidates a
        detection. We compare duration, average power, and energy to
        reject similar false positives.

        Args:
            detections: List of detections to filter

        Returns:
            Filtered list of detections (false positives removed)
        """
        if not detections:
            return []

        # Load negative signatures from the database
        negative_sigs = {}
        try:
            with db_manager.engine.connect() as conn:
                query = text(
                    """
                    SELECT
                        cs.id,
                        cs.appliance_id,
                        cs.start_time,
                        cs.end_time,
                        (
                            SELECT AVG(papp)
                            FROM linky_realtime
                            WHERE time >= cs.start_time
                              AND time <= cs.end_time
                        ) as avg_power,
                        EXTRACT(EPOCH FROM (cs.end_time - cs.start_time)) as duration_s
                    FROM nilm_signatures cs
                    WHERE is_negative = TRUE
                    ORDER BY created_at DESC
                """
                )

                result = conn.execute(query)

                for row in result:
                    sig_id, app_id, start_t, end_t, avg_pwr, duration_s = row
                    duration = int(float(duration_s)) if duration_s else int((end_t - start_t).total_seconds())
                    avg_power = float(avg_pwr) if avg_pwr else 0.0
                    # energy = avg_power * real_duration / 3600  (same formula as PATH A)
                    energy = avg_power * duration / 3600.0

                    if app_id not in negative_sigs:
                        negative_sigs[app_id] = []

                    negative_sigs[app_id].append(
                        {
                            "id": sig_id,
                            "duration_seconds": duration,
                            "avg_power": avg_power,
                            "energy_wh": energy,
                        }
                    )

                total_negs = sum(len(s) for s in negative_sigs.values())
                if total_negs > 0:
                    logger.info(f"Filtering against {total_negs} negative signatures")
        except Exception as e:
            logger.error(f"Error loading negative signatures: {e}")
            return detections  # Return unfiltered on error

        # Filter the detections
        filtered = []
        rejected_count = 0

        for det in detections:
            app_id = det["appliance_id"]
            negs = negative_sigs.get(app_id, [])

            if not negs:
                # No negative signatures for this appliance
                filtered.append(det)
                continue

            is_false_positive = False

            # DEBUG: log the detection being analyzed
            logger.info(f"Analyzing detection: {det['duration_seconds']}s, " f"{det['avg_power']:.1f}W, {det.get('energy_wh', 0):.1f}Wh")

            for neg in negs:
                # Criterion 1: similar duration (±50%, since these are change points)
                duration_ratio = det["duration_seconds"] / neg["duration_seconds"] if neg["duration_seconds"] > 0 else 0

                # DEBUG: detailed comparison log
                logger.debug(
                    f"  vs negative signature #{neg['id']}: " f"{neg['duration_seconds']:.0f}s, " f"{neg['avg_power']:.1f}W, {neg['energy_wh']:.1f}Wh"
                )
                logger.debug(f"Ratios: duration={duration_ratio:.2f}, " f"thresholds=[0.50, 1.50]")

                if not (0.50 <= duration_ratio <= 1.50):
                    logger.debug("Duration out of range")
                    continue

                logger.debug("Duration OK")

                # Criterion 2: similar average power (±15%, relaxed)
                if neg["avg_power"] > 0:
                    power_ratio = det["avg_power"] / neg["avg_power"]
                    logger.debug(f"Power: ratio={power_ratio:.2f}, " f"thresholds=[0.85, 1.15]")
                    if not (0.85 <= power_ratio <= 1.15):
                        logger.debug("Power out of range")
                        continue
                    logger.debug("Power OK")

                # Criterion 3: similar energy (±20%, relaxed)
                det_energy = det.get("energy_wh", 0)
                if neg["energy_wh"] > 0 and det_energy > 0:
                    energy_ratio = det_energy / neg["energy_wh"]
                    logger.debug(f"Energy: ratio={energy_ratio:.2f}, " f"thresholds=[0.80, 1.20]")
                    if not (0.80 <= energy_ratio <= 1.20):
                        logger.debug("Energy out of range")
                        continue
                    logger.debug("Energy OK")

                # All criteria match -> false positive
                is_false_positive = True
                logger.debug(
                    f"Detection rejected (similar to negative "
                    f"signature #{neg['id']}): {det.get('appliance_name')} - "
                    f"{det['duration_seconds']}s, "
                    f"{det['avg_power']:.1f}W"
                )
                break

            if not is_false_positive:
                filtered.append(det)
            else:
                rejected_count += 1

        if rejected_count > 0:
            logger.info(f"Filtering complete: {rejected_count} false positives " f"rejected, {len(filtered)} detections kept")

        return filtered

    def _load_signature_profiles(self):
        """
        Load signature profiles from the database.
        Includes morphological data if available.

        Used for pattern matching during detection.
        """
        import json as json_module

        with db_manager.get_session() as session:
            # Fetch active appliances with their signatures
            appliances_query = """
                SELECT DISTINCT appliance_id, ca.name
                FROM nilm_signatures cs
                JOIN nilm_appliances ca ON cs.appliance_id = ca.id
            """
            appliances = session.execute(text(appliances_query)).fetchall()

            for appliance_id, appliance_name in appliances:
                # Fetch signatures with morphology_analysis
                sig_query = """
                    SELECT
                        id,
                        start_time,
                        end_time,
                        power_data,
                        morphology_analysis
                    FROM nilm_signatures
                    WHERE appliance_id = :appliance_id
                      AND is_negative = FALSE
                    ORDER BY created_at
                """
                signatures = session.execute(text(sig_query), {"appliance_id": appliance_id}).fetchall()

                for row in signatures:
                    sig_id = row[0]
                    start_time = row[1]
                    end_time = row[2]
                    power_data_json = row[3]
                    morphology_json = row[4]

                    # Load power_data from JSON or linky_realtime
                    appliance_power = None

                    if power_data_json:
                        # Use stored power_data
                        try:
                            power_data = json_module.loads(power_data_json)
                            appliance_power = np.array(power_data.get("values", []))
                        except Exception as e:
                            logger.warning(f"Error reading power_data " f"for sig {sig_id}: {e}")

                    # Fallback: load from linky_realtime
                    if appliance_power is None or len(appliance_power) == 0:
                        signature = {"id": sig_id, "appliance_id": appliance_id, "start_time": start_time, "end_time": end_time}
                        aggregate_power, appliance_power = Seq2PointMultiOutputModel._load_signature_data_static(signature)

                    if appliance_power is None or len(appliance_power) == 0:
                        continue

                    duration = int((end_time - start_time).total_seconds())

                    # Parse morphology_analysis
                    morphology = None
                    if morphology_json:
                        try:
                            morphology = json_module.loads(morphology_json)
                        except Exception as e:
                            logger.warning(f"Error reading morphology " f"for sig {sig_id}: {e}")

                    # Add the profile with morphology
                    self.change_point_detector.add_signature_profile(
                        appliance_id=appliance_id,
                        appliance_name=appliance_name,
                        power_sequence=appliance_power,
                        duration=duration,
                        signature_id=sig_id,
                        morphology=morphology,
                    )

        total_profiles = sum(len(data["profiles"]) for data in self.change_point_detector.signature_profiles.values())
        logger.info(f"Profiles loaded: " f"{len(self.change_point_detector.signature_profiles)} " f"appliances, {total_profiles} profiles")

    def disaggregate(self, start_time, end_time):
        """
        Disaggregate total consumption across all appliances.
        Uses the Multi-Output architecture with hybrid detection.

        Args:
            start_time: Period start
            end_time: Period end

        Returns:
            List of detections per appliance
        """
        if self.multioutput_model is None:
            logger.error("No Multi-Output model loaded for disaggregation")
            return []

        # Load signature profiles if needed
        if not self.change_point_detector.signature_profiles:
            logger.info("Loading signature profiles for detection...")
            self._load_signature_profiles()

        try:
            # Load total consumption
            with db_manager.get_session() as session:
                query = """
                    SELECT time, papp
                    FROM linky_realtime
                    WHERE time >= :start_time AND time <= :end_time
                    ORDER BY time
                """
                result = session.execute(text(query), {"start_time": start_time, "end_time": end_time})
                data = result.fetchall()
                if not data:
                    logger.warning("No data for disaggregation")
                    return []
                timestamps = [row[0] for row in data]
                aggregate_power = np.array([row[1] for row in data], dtype=np.float32)
            logger.info(f"Disaggregating over {len(aggregate_power)} points")

            ##########################################################
            # HYBRID APPROACH: Change Point Detection + Pattern Matching
            ##########################################################

            logger.info("=== Hybrid Detection " "(Change Point + Pattern Matching) ===")

            # Step 1: detect change points in the aggregate
            change_points = self.change_point_detector.detect_change_points(aggregate_power)

            if not change_points:
                logger.warning("No change point detected")
                return []

            # Step 2: extract patterns (timestamps -> duration in real seconds)
            patterns = self.change_point_detector.extract_patterns(
                aggregate_power, change_points, timestamps=timestamps
            )

            # ─── PATH A: Change Point + Pattern Matching ─────────────────────
            path_a_detections = []
            if patterns:
                for pattern_data in patterns:
                    match_result = self.change_point_detector.match_pattern(
                        pattern_data, pattern_morphology=pattern_data.get("morphology")
                    )
                    if match_result:
                        (appliance_id, appliance_name, matched_signature_id, confidence) = match_result
                        start_idx = pattern_data["start_idx"]
                        end_idx = pattern_data["end_idx"]
                        if start_idx < len(timestamps) and end_idx <= len(timestamps):
                            det = {
                                "appliance_id": appliance_id,
                                "appliance_name": appliance_name,
                                "signature_id": matched_signature_id,
                                "start_time": timestamps[start_idx],
                                "end_time": timestamps[min(end_idx, len(timestamps) - 1)],
                                "duration_seconds": pattern_data["duration"],  # real seconds
                                "avg_power": pattern_data["avg_power"],
                                "max_power": pattern_data["max_power"],
                                "energy_wh": pattern_data["energy_wh"],
                                "confidence_score": float(confidence),
                                "features": {
                                    "detection_method": "change_point_pattern_matching",
                                    "change_point_based": True,
                                },
                            }
                            if matched_signature_id is not None:
                                det["features"]["matched_signature_id"] = int(matched_signature_id)
                                det["features"]["matching"] = {
                                    "score": float(confidence),
                                    "method": "energy_duration_power_shape",
                                }
                            path_a_detections.append(det)
                            logger.info(
                                f"PATH A match: {appliance_name} "
                                f"{pattern_data['duration']:.0f}s "
                                f"{pattern_data['avg_power']:.0f}W "
                                f"{pattern_data['energy_wh']:.2f}Wh "
                                f"conf={confidence:.2%}"
                            )
            else:
                logger.info("PATH A: no pattern extracted (no clear change points)")

            logger.info(f"PATH A: {len(path_a_detections)} detections")

            # ─── PATH B: Seq2Point Sliding Window Inference ──────────────────
            # Detects complex cycles (washing machine, fridge, oven) that
            # change points don't capture well.
            path_b_detections = []
            try:
                # Estimated sampling interval
                if len(timestamps) > 1:
                    sample_interval = (timestamps[-1] - timestamps[0]).total_seconds() / (len(timestamps) - 1)
                else:
                    sample_interval = 8.0
                min_duration_samples = max(1, int(settings.nilm_min_duration_seconds / sample_interval))

                # Adaptive stride: larger = faster on the Pi, less precise
                stride = max(1, min(10, len(aggregate_power) // 5000))
                logger.info(f"PATH B: Seq2Point inference stride={stride} ({len(aggregate_power)} pts)")

                predictions_dict = self.multioutput_model.predict(aggregate_power, stride=stride)

                for app_id, signal in predictions_dict.items():
                    # Name and expected power from signature profiles
                    app_name = f"appliance_{app_id}"
                    expected_power = None
                    for aid, pdata in self.change_point_detector.signature_profiles.items():
                        if aid == app_id:
                            app_name = pdata["name"]
                            powers = [p["avg_power"] for p in pdata["profiles"]]
                            if powers:
                                expected_power = float(np.median(powers))
                            break

                    # Adaptive threshold: 30% of expected power, min 50 W
                    threshold_w = max(50.0, (expected_power or settings.nilm_min_power_threshold) * 0.30)

                    # Noise-smoothing (window = ~1/4 of the min duration)
                    smooth_w = max(3, min_duration_samples // 4)
                    signal_smooth = np.convolve(signal, np.ones(smooth_w) / smooth_w, mode="same")
                    signal_smooth = np.maximum(signal_smooth, 0)

                    active_mask = signal_smooth > threshold_w
                    segments = self._find_active_segments(
                        active_mask, timestamps, signal_smooth, min_duration_samples
                    )

                    for seg in segments:
                        seg["appliance_id"] = app_id
                        seg["appliance_name"] = app_name
                        seg["features"] = {
                            "detection_method": "seq2point_inference",
                            "change_point_based": False,
                        }
                        path_b_detections.append(seg)

                    if segments:
                        logger.info(f"PATH B: {app_name} → {len(segments)} segments")

            except Exception as e:
                logger.warning(f"PATH B failed (non-blocking): {e}", exc_info=True)

            logger.info(f"PATH B: {len(path_b_detections)} detections")

            # ─── MERGE + DEDUP ─────────────────────────────────────────────────
            all_detections = path_a_detections + path_b_detections
            all_detections = self._dedup_detections(all_detections)

            logger.info(f"Total after merge/dedup: {len(all_detections)}")

            # Filter out negative signatures
            all_detections = self._filter_against_negative_signatures(all_detections)

            # Confidence threshold lowered (the user validates in the UI)
            min_confidence = 0.25
            before = len(all_detections)
            all_detections = [d for d in all_detections if d.get("confidence_score", 0) >= min_confidence]
            if before > len(all_detections):
                logger.info(f"Confidence filtering: {before - len(all_detections)} rejected (<{min_confidence:.0%})")

            logger.info(f"Total final detections: {len(all_detections)}")
            return all_detections

        except Exception as e:
            logger.error(f"Disaggregation error: {e}", exc_info=True)
            return []

    def _dedup_detections(self, detections):
        """
        Merge duplicate detections between PATH A and PATH B.

        Two detections of the same appliance that overlap by more than 50%
        of the shorter one's duration are treated as the same event. The
        one with the higher confidence score is kept.
        """
        if not detections:
            return []

        # Group by appliance_id
        by_appliance = {}
        for d in detections:
            app_id = d["appliance_id"]
            by_appliance.setdefault(app_id, []).append(d)

        merged = []
        for app_id, dets in by_appliance.items():
            # Sort by start_time
            sorted_dets = sorted(dets, key=lambda d: d["start_time"])
            kept = []
            for d in sorted_dets:
                duplicate = False
                for k in kept:
                    latest_start = max(d["start_time"], k["start_time"])
                    earliest_end = min(d["end_time"], k["end_time"])
                    if latest_start >= earliest_end:
                        continue
                    overlap_s = (earliest_end - latest_start).total_seconds()
                    dur_d = (d["end_time"] - d["start_time"]).total_seconds()
                    dur_k = (k["end_time"] - k["start_time"]).total_seconds()
                    shorter = min(dur_d, dur_k)
                    if shorter > 0 and overlap_s / shorter > 0.50:
                        # Duplicate — keep the higher score
                        if d.get("confidence_score", 0) > k.get("confidence_score", 0):
                            kept.remove(k)
                            kept.append(d)
                        duplicate = True
                        break
                if not duplicate:
                    kept.append(d)
            merged.extend(kept)

        return sorted(merged, key=lambda d: d["start_time"])

    def _merge_consecutive_cycles(self, cycles, max_gap_seconds=120):
        """
        Merge consecutive cycles separated by less than max_gap_seconds.
        Generic: works for any appliance.

        Args:
            cycles: List of cycles detected by KMeans
            max_gap_seconds: Max gap in seconds to merge two cycles

        Returns:
            List of merged cycles
        """
        if not cycles or len(cycles) == 0:
            return []

        # Sort cycles by start_idx
        sorted_cycles = sorted(cycles, key=lambda c: c["start_idx"])

        merged = []
        current_merged = sorted_cycles[0].copy()

        for i in range(1, len(sorted_cycles)):
            cycle = sorted_cycles[i]

            # Compute the gap between the current merged cycle's end and the next one's start
            gap = cycle["start_idx"] - current_merged["end_idx"]

            if gap <= max_gap_seconds:
                # Merge: extend the current cycle
                current_merged["end_idx"] = cycle["end_idx"]
                current_merged["duration_seconds"] = current_merged["end_idx"] - current_merged["start_idx"]
                # Recompute avg_power and max_power (weighted average)
                # Note: we keep the higher max_power
                current_merged["max_power"] = max(current_merged["max_power"], cycle["max_power"])
                # For avg_power, use a simple average (approximation)
                current_merged["avg_power"] = (current_merged["avg_power"] + cycle["avg_power"]) / 2
                # Sum the energy
                current_merged["energy_wh"] = current_merged["energy_wh"] + cycle["energy_wh"]
            else:
                # Gap too large: save the current merged cycle and start a new one
                merged.append(current_merged)
                current_merged = cycle.copy()

        # Add the last merged cycle
        merged.append(current_merged)

        return merged

    def _find_active_segments(self, active_mask, timestamps, predictions, min_duration):
        """
        Find active segments in the predictions, detecting gaps to split
        long periods into individual cycles.

        Args:
            active_mask: Boolean mask of active predictions
            timestamps: Corresponding timestamps
            predictions: Power predictions
            min_duration: Minimum duration in seconds

        Returns:
            List of active segments
        """
        segments = []

        # Padding to handle indices
        half_window = (settings.effective_sequence_length - 1) // 2

        # Gap detection parameters (inactive periods between two cycles)
        # A gap is detected if power stays < 20% of the threshold for min_gap_duration
        # For a water heater (3500W), a gap = power < 100W
        gap_threshold = settings.nilm_min_power_threshold * 0.2  # 20% of threshold (= 100W with threshold=500W)
        min_gap_duration = 120  # 2 minutes minimum to consider a real gap (end of heating cycle)

        in_segment = False
        start_idx = 0
        gap_start = None

        for i in range(len(active_mask)):
            current_power = predictions[i] if i < len(predictions) else 0

            if active_mask[i] and not in_segment:
                # Start of a new segment
                in_segment = True
                start_idx = i
                gap_start = None

            elif in_segment:
                # Inside an active segment
                if current_power < gap_threshold:
                    # Low power, potential start of a gap
                    if gap_start is None:
                        gap_start = i
                    elif (i - gap_start) >= min_gap_duration:
                        # Gap confirmed: end of the current segment
                        duration = gap_start - start_idx

                        if duration >= min_duration:
                            # Record the segment before the gap
                            orig_start = start_idx + half_window
                            orig_end = gap_start + half_window

                            if orig_start < len(timestamps) and orig_end <= len(timestamps):
                                segment_predictions = predictions[start_idx:gap_start]

                                segment = {
                                    "start_time": timestamps[orig_start],
                                    "end_time": timestamps[min(orig_end, len(timestamps) - 1)],
                                    "duration_seconds": duration,
                                    "avg_power": float(np.mean(segment_predictions)),
                                    "max_power": float(np.max(segment_predictions)),
                                    "energy_wh": float(np.sum(segment_predictions) / 3600),
                                    "confidence_score": (
                                        float(np.mean(segment_predictions) / np.max(predictions)) if np.max(predictions) > 0 else 0.0
                                    ),
                                }
                                segments.append(segment)

                        # Reset to look for the next segment
                        in_segment = False
                        start_idx = i
                        gap_start = None
                else:
                    # High power, reset the gap counter
                    gap_start = None

                # Also check whether we're leaving the active mask (standard case)
                if not active_mask[i]:
                    duration = i - start_idx

                    if duration >= min_duration:
                        orig_start = start_idx + half_window
                        orig_end = i + half_window

                        if orig_start < len(timestamps) and orig_end <= len(timestamps):
                            segment_predictions = predictions[start_idx:i]

                            segment = {
                                "start_time": timestamps[orig_start],
                                "end_time": timestamps[min(orig_end, len(timestamps) - 1)],
                                "duration_seconds": duration,
                                "avg_power": float(np.mean(segment_predictions)),
                                "max_power": float(np.max(segment_predictions)),
                                "energy_wh": float(np.sum(segment_predictions) / 3600),
                                "confidence_score": (float(np.mean(segment_predictions) / np.max(predictions)) if np.max(predictions) > 0 else 0.0),
                            }
                            segments.append(segment)

                    in_segment = False
                    gap_start = None

        # Last segment if still active
        if in_segment:
            duration = len(active_mask) - start_idx
            if duration >= min_duration:
                orig_start = start_idx + half_window
                orig_end = len(active_mask) + half_window

                if orig_start < len(timestamps):
                    segment_predictions = predictions[start_idx:]

                    segment = {
                        "start_time": timestamps[orig_start],
                        "end_time": timestamps[min(orig_end, len(timestamps) - 1)],
                        "duration_seconds": duration,
                        "avg_power": float(np.mean(segment_predictions)),
                        "max_power": float(np.max(segment_predictions)),
                        "energy_wh": float(np.sum(segment_predictions) / 3600),
                        "confidence_score": (float(np.mean(segment_predictions) / np.max(predictions)) if np.max(predictions) > 0 else 0.0),
                    }
                    segments.append(segment)

        return segments
