"""
Change point detection and pattern matching for NILM.
"""

import logging

import numpy as np


logger = logging.getLogger(__name__)


class ChangePointPatternDetector:
    """
    Détecteur hybride combinant change point detection et pattern matching.

    Approche :
    1. Détecte les change points (sauts significatifs) dans l'agrégé
    2. Extrait les patterns entre les baselines
    3. Compare avec les profiles de signatures connus
    4. Reconstruit des cycles complets
    """

    def __init__(self, min_power_change=500, min_duration=300):
        """
        Args:
            min_power_change: Seuil minimal pour détecter un change point (W)
            min_duration: Durée minimale d'un pattern (secondes)
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
        Ajoute un profil de signature avec analyse morphologique.

        Args:
            appliance_id: ID de l'appareil
            appliance_name: Nom de l'appareil
            power_sequence: Séquence de puissance
            duration: Durée en secondes
            signature_id: ID de la signature (optional)
            morphology: Analyse morphologique (optional)
        """
        if appliance_id not in self.signature_profiles:
            self.signature_profiles[appliance_id] = {
                "name": appliance_name,
                "profiles": [],
            }

        # Normaliser le profil (0-1)
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

                # Ajouter features morphologiques si available
                if morphology:
                    profile["morphology"] = morphology

                self.signature_profiles[appliance_id]["profiles"].append(profile)

    def detect_change_points(self, aggregate_power):
        """
        Détecte les change points dans la consommation agrégée.

        Utilise un algorithme basé sur le gradient et la variance locale.

        Args:
            aggregate_power: Consommation agrégée

        Returns:
            Liste de change points avec indices et amplitudes
        """
        if len(aggregate_power) < 10:
            return []

        # Calculer le gradient (dérivée discrète)
        gradient = np.diff(aggregate_power)

        # Lisser pour éviter le bruit (moyenne mobile sur 5 points)
        window_size = 5
        if len(gradient) >= window_size:
            gradient_smooth = np.convolve(gradient, np.ones(window_size) / window_size, mode="valid")
        else:
            gradient_smooth = gradient

        # Détecter les sauts significatifs
        change_points = []
        threshold = self.min_power_change

        i = 0
        while i < len(gradient_smooth):
            # Chercher un saut significatif
            if abs(gradient_smooth[i]) > threshold / 10:  # Détection initiale sensible
                # Vérifier si c'est un vrai saut (somme sur fenêtre)
                window_end = min(i + 30, len(gradient_smooth))  # Fenêtre de 30s
                cumsum = np.sum(gradient_smooth[i:window_end])

                if abs(cumsum) > threshold:
                    # Change point détecté
                    change_points.append(
                        {
                            "index": i + window_size // 2,
                            "amplitude": float(cumsum),
                            "direction": "up" if cumsum > 0 else "down",
                        }
                    )  # Ajuster pour le lissage
                    # Sauter la fenêtre pour éviter les doublons
                    i = window_end
                    continue
            i += 1

        logger.info(f"Change points détectés: {len(change_points)}")
        return change_points

    def extract_patterns(self, aggregate_power, change_points, timestamps=None):
        """
        Extrait les patterns entre les change points.

        Args:
            aggregate_power: Consommation agrégée
            change_points: Change points détectés
            timestamps: Liste de timestamps correspondant à aggregate_power (optionnel)
                        Quand fourni, la durée est calculée en vraies secondes.
                        Quand absent, estimation depuis le taux d'échantillonnage.

        Returns:
            Liste de patterns avec séquences et métadonnées
        """
        from ..morphology import MorphologyAnalyzer

        if len(change_points) < 2:
            return []

        # Estimer l'intervalle d'échantillonnage (secondes/sample)
        if timestamps and len(timestamps) > 1:
            total_seconds = (timestamps[-1] - timestamps[0]).total_seconds()
            sample_interval = total_seconds / max(len(timestamps) - 1, 1)
        else:
            # Fallback: hypothèse 8s/sample (HA Linky typique)
            sample_interval = 8.0

        # min_duration est en secondes → convertir en samples pour le filtre initial
        min_duration_samples = max(1, int(self.min_duration / sample_interval))

        patterns = []
        analyzer = MorphologyAnalyzer()

        # Regrouper les change points en segments
        i = 0
        while i < len(change_points):
            cp = change_points[i]

            if cp["direction"] == "up":
                # Chercher le change point DOWN correspondant
                end_idx = None
                for j in range(i + 1, len(change_points)):
                    if change_points[j]["direction"] == "down":
                        end_idx = j
                        break

                if end_idx is not None:
                    start = cp["index"]
                    end = change_points[end_idx]["index"]
                    duration_samples = end - start

                    # Durée en vraies secondes (corrige le bug unité)
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
                                logger.warning(f"Erreur calcul morphologie pattern: {e}")
                                morphology = None

                            # Énergie correcte : puissance_moyenne × durée_réelle / 3600
                            energy_wh = float(np.mean(pattern)) * duration_seconds / 3600.0

                            patterns.append(
                                {
                                    "start_idx": start,
                                    "end_idx": end,
                                    "duration": duration_seconds,   # secondes (corrigé)
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

        logger.info(f"Patterns extraits: {len(patterns)} (intervalle ~{sample_interval:.1f}s/pt)")
        return patterns

    def match_pattern(self, pattern_data, pattern_morphology=None):
        """
        Compare un pattern avec les profiles de signatures connus.
        Utilise features morphologiques si available pour meilleur matching.

        Args:
            pattern_data: Données du pattern à matcher
            pattern_morphology: Analyse morphologique du pattern (optional)

        Returns:
            (appliance_id, appliance_name, signature_id, confidence) ou None
        """
        if not self.signature_profiles:
            return None

        pattern = pattern_data["pattern"]
        pattern_duration = pattern_data["duration"]    # secondes (corrigé)
        pattern_power = pattern_data["avg_power"]
        pattern_energy = pattern_data.get("energy_wh", 0.0)

        # Normaliser le pattern (0-1)
        pattern_max = np.max(pattern)
        if pattern_max == 0:
            return None
        pattern_normalized = pattern / pattern_max

        best_match = None
        best_score = 0.0

        for appliance_id, data in self.signature_profiles.items():
            appliance_name = data["name"]
            logger.info(
                f"Comparaison pattern ({pattern_duration:.0f}s, {pattern_power:.0f}W, "
                f"{pattern_energy:.2f}Wh) avec {len(data['profiles'])} profiles de {appliance_name}"
            )

            for i, profile in enumerate(data["profiles"]):
                # --- Filtre durée : ±75% (large pour gérer lave-linge/ballon variables) ---
                if profile["duration"] <= 0:
                    continue
                duration_ratio = pattern_duration / profile["duration"]
                if duration_ratio < 0.25 or duration_ratio > 4.0:
                    continue

                # --- Filtre puissance : ±40% ---
                if profile["avg_power"] <= 0:
                    continue
                power_ratio = pattern_power / profile["avg_power"]
                if power_ratio < 0.60 or power_ratio > 1.40:
                    continue

                # --- Score durée et puissance ---
                duration_score = max(0.0, 1.0 - abs(1.0 - duration_ratio) / 2.0)
                power_score = max(0.0, 1.0 - abs(1.0 - power_ratio))

                # --- Score énergie (plus stable que puissance seule) ---
                profile_energy = profile.get("energy_wh", 0.0)
                if profile_energy > 0 and pattern_energy > 0:
                    energy_ratio = pattern_energy / profile_energy
                    energy_score = max(0.0, 1.0 - abs(1.0 - energy_ratio) / 2.0)
                else:
                    energy_score = 0.5  # neutre si pas de données énergie

                # --- Corrélation de forme ---
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

                # --- Score morphologique si disponible ---
                morphology_score = 0.0
                has_morphology = pattern_morphology and "morphology" in profile
                if has_morphology:
                    morphology_score = self._compute_morphology_similarity(
                        pattern_morphology, profile["morphology"]
                    )

                # --- Score combiné ---
                # Énergie = feature la plus stable toutes typologies confondues
                # Durée  = contrainte forte (bornes larges dans le filtre)
                # Puissance = contrainte secondaire
                # Forme = bonus (bruit sur données réelles)
                # Morphologie = bonus si disponible
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
                    f"  Profil#{i}: energy={energy_score:.3f}, dur={duration_score:.3f}, "
                    f"pow={power_score:.3f}, corr={abs_correlation:.3f}, "
                    f"morpho={morphology_score:.3f} → combined={combined_score:.3f}"
                )

                if combined_score > best_score:
                    best_score = combined_score
                    best_match = (
                        appliance_id,
                        appliance_name,
                        profile.get("signature_id"),
                        combined_score,
                    )

        # Seuil bas : mieux vaut un faux positif qu'un faux négatif (l'utilisateur valide)
        threshold = 0.25

        logger.info(f"Fin matching: best_score={best_score:.3f}, seuil={threshold}")

        if best_match and best_match[3] > threshold:
            logger.info(
                f"✓ Match trouvé: {best_match[1]} "
                f"(sig_id={best_match[2]}, confiance={best_match[3]:.3f})"
            )
            return best_match
        else:
            logger.info(f"✗ Aucun match (best={best_score:.3f} < {threshold})")
            return None

    def _compute_morphology_similarity(self, morpho1, morpho2):
        """
        Calcule similarité entre deux analyses morphologiques.

        Args:
            morpho1: Première analyse morphologique
            morpho2: Deuxième analyse morphologique

        Returns:
            Score de similarité [0-1]
        """
        score = 0.0
        weight_sum = 0.0

        # 1. Pattern type match (poids: 0.3)
        if "shape_features" in morpho1 and "shape_features" in morpho2:
            type1 = morpho1["shape_features"].get("pattern_type", "")
            type2 = morpho2["shape_features"].get("pattern_type", "")
            if type1 == type2:
                score += 0.3
            weight_sum += 0.3

        # 2. Oscillation features (poids: 0.25)
        if "oscillation_features" in morpho1 and "oscillation_features" in morpho2:
            osc1 = morpho1["oscillation_features"]
            osc2 = morpho2["oscillation_features"]

            # Les deux oscillent ou les deux n'oscillent pas
            if osc1.get("is_oscillating") == osc2.get("is_oscillating"):
                osc_score = 0.25

                # Si les deux oscillent, comparer fréquence
                if osc1.get("is_oscillating"):
                    freq1 = osc1.get("oscillation_frequency_hz", 0)
                    freq2 = osc2.get("oscillation_frequency_hz", 0)
                    if freq2 > 0:
                        freq_ratio = min(freq1, freq2) / max(freq1, freq2)
                        osc_score *= freq_ratio

                score += osc_score
            weight_sum += 0.25

        # 3. Gradient features (poids: 0.2)
        if "gradient" in morpho1 and "gradient" in morpho2:
            grad1 = morpho1["gradient"]
            grad2 = morpho2["gradient"]

            # Comparer max rise rate
            rise1 = grad1.get("max_rise_rate", 0)
            rise2 = grad2.get("max_rise_rate", 0)
            if max(rise1, rise2) > 0:
                rise_sim = min(rise1, rise2) / max(rise1, rise2)
                score += rise_sim * 0.1

            # Comparer max fall rate
            fall1 = abs(grad1.get("max_fall_rate", 0))
            fall2 = abs(grad2.get("max_fall_rate", 0))
            if max(fall1, fall2) > 0:
                fall_sim = min(fall1, fall2) / max(fall1, fall2)
                score += fall_sim * 0.1

            weight_sum += 0.2

        # 4. Plateaus similarity (poids: 0.15)
        if "plateaus" in morpho1 and "plateaus" in morpho2:
            plat1 = morpho1["plateaus"]
            plat2 = morpho2["plateaus"]

            # Comparer nombre de plateaux
            num1 = len(plat1) if plat1 else 0
            num2 = len(plat2) if plat2 else 0

            if max(num1, num2) > 0:
                num_sim = min(num1, num2) / max(num1, num2)
                score += num_sim * 0.15
            else:
                # Les deux n'ont pas de plateaux = similarité
                score += 0.15

            weight_sum += 0.15

        # 5. Statistical moments (poids: 0.1)
        if "statistical_moments" in morpho1 and "statistical_moments" in morpho2:
            stat1 = morpho1["statistical_moments"]
            stat2 = morpho2["statistical_moments"]

            # Comparer skewness (signe de l'asymétrie)
            skew1 = stat1.get("skewness", 0)
            skew2 = stat2.get("skewness", 0)

            # Même signe d'asymétrie = bon
            if (skew1 * skew2) >= 0:
                score += 0.1

            weight_sum += 0.1

        # Normaliser par le poids total
        if weight_sum > 0:
            return score / weight_sum
        else:
            return 0.0
