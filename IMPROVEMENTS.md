# Améliorations NILM - Phase 1 & 2

## Résumé des changements

Cette branche implémente les améliorations critiques pour résoudre le problème de non-détection du "Chauffage à bain d'huile".

### Problème identifié
Le modèle NILM ne détecte pas le chauffage malgré 14 signatures, principalement à cause de:
1. Chevauchement temporel à 90% avec le Ballon d'Eau Chaude
2. Architecture FiLM inadaptée aux appareils concurrents (un seul output conditionné)
3. Filtres trop agressifs (confiance 55%, signatures négatives ±5%/±10%)
4. Stride trop élevé (réduction des exemples d'entraînement)

## Phase 1 - Quick Wins ⚡

### 1.1 Configuration optimisée
- **sequence_length**: 299 → **599** (fenêtre de 10 minutes au lieu de 5)
  - Capture les cycles complets du chauffage (montée + plateau + descente)
- **min_power_threshold**: 30W → **15W**
  - Détecte les transitions douces du chauffage
- **cnn_sequence_length**: Explicitement défini à 599 dans config.py

### 1.2 Filtres assouplis
- **min_confidence**: 0.55 → **0.40** (40% minimum)
  - Moins de rejets pour les détections incertaines
- **Signatures négatives**:
  - Puissance: ±5% → **±15%**
  - Énergie: ±10% → **±20%**
  - Moins de faux rejets pour appareils similaires

### 1.3 Stride réduit
- **Positifs**: stride 30 → **10**
- **Négatifs**: stride 50 → **15**
- **Impact**: 3x plus d'exemples d'entraînement
- Améliore la diversité et la robustesse du modèle

## Phase 2 - Architecture Multi-Output 🏗️

### 2.1 Nouvelle classe `Seq2PointMultiOutputModel`
Remplace FiLM par une architecture à sorties parallèles:

```python
Architecture:
  Input: aggregate_power (599, 1)
  ↓
  Conv1D (64 filters, kernel=5)
  ↓
  GRU/LSTM (128 → 64 units)
  ↓
  Multi-Head Attention (4 heads, key_dim=16)
  ↓
  Shared Dense (128 → 64)
  ↓
  Output branches (1 par appareil)
    ├─ output_Ballon_dEau_Chaude
    ├─ output_Chauffage_a_bain_dhuile
    └─ ...
```

**Avantages vs FiLM**:
- ✅ Désagrégation simultanée de N appareils
- ✅ Détection native des chevauchements temporels
- ✅ Pas de conditioning (plus simple)
- ✅ Mieux adapté au cas Chauffage + Ballon

### 2.2 Multi-Head Attention
- Capture les patterns simultanés de plusieurs appareils
- 4 têtes d'attention pour diversifier les features
- Essentiel pour distinguer chauffage et ballon

### 2.3 Class Weighting
- Poids inversement proportionnel au nombre de signatures
- Compense le déséquilibre (14 chauffage vs 40+ ballon)
- Empêche le biais vers l'appareil dominant

### 2.4 Réduction false_positive_penalty
- **asymmetric_loss**: penalty 2.5 → **1.5**
- Moins agressif sur les faux positifs
- Permet au modèle d'être plus "audacieux"

## Configuration requise

### Variables d'environnement (.env)
```bash
# Activer l'architecture Multi-Output
NILM_ARCHITECTURE=multioutput  # ou 'film' pour l'ancienne version

# Type de modèle (optionnel)
NILM_MODEL_TYPE=gru  # ou 'lstm'
```

## Tests et validation

### Compilation
```bash
cd nilm-cnn-service
python -m py_compile src/seq2point_nilm.py src/config.py
# ✅ Aucune erreur
```

### Entraînement
```bash
# Dans Docker
docker compose exec nilm-cnn-service python -m tasks train

# Logs attendus:
# 🎯 Architecture: MULTIOUTPUT, Type: GRU
# 📊 Class weights:
#    Chauffage à bain d'huile: 2.85 (14 samples)
#    Ballon d'Eau Chaude: 0.35 (40 samples)
# 🎬 Entraînement Multi-Output (outputs parallèles + attention)
```

### Détection
```bash
docker compose exec nilm-cnn-service python -m tasks detect

# Vérifier dans les logs:
# - Change points détectés
# - Patterns extraits
# - Détections du chauffage avec confiance >= 40%
```

## Métriques à surveiller

1. **Détections du chauffage**: Devrait augmenter significativement
2. **Confiance moyenne**: Peut baisser (normal avec seuil 40%)
3. **Faux positifs**: Possiblement plus élevés (trade-off acceptable)
4. **Overlap handling**: Chauffage ET ballon détectés simultanément

## Rollback

Si problèmes, revenir à FiLM:
```bash
# .env
NILM_ARCHITECTURE=film
```

Ou revenir au commit précédent:
```bash
git checkout main
```

## Prochaines étapes (Phase 3 - optionnel)

1. **Signatures pures**: Créer des labels où seul le chauffage fonctionne
2. **Data augmentation**: Bruit gaussien, time-shifting, variations amplitude
3. **K-Fold CV**: Utiliser tous les folds au lieu du dernier uniquement
4. **Métriques détaillées**: Precision/Recall/F1 par appareil
5. **Fine-tuning hyperparamètres**: Learning rate, dropout, attention heads

## Notes techniques

- Backward compatible avec FiLM
- Les deux architectures cohabitent dans le code
- Le choix se fait via `NILM_ARCHITECTURE`
- Les métadonnées du modèle stockent l'architecture utilisée
