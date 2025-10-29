# Temporal Validation Branches

Ce document explique les deux implémentations alternatives de validation temporelle pour le système NILM.

## Problème résolu

**Actuellement** (branche `main`), la validation utilise `train_test_split` avec un split **aléatoire** :
- ❌ Data leakage temporel (le modèle voit des données "futures" pendant l'entraînement)
- ❌ Pas de test de généralisation sur le futur
- ❌ Métriques de validation trop optimistes

## Solution 1 : Split temporel simple (80/20)

**Branche** : `feature/temporal-train-val-split`

### Principe
- 80% des données **les plus anciennes** pour l'entraînement
- 20% des données **les plus récentes** pour la validation
- Split chronologique basé sur les timestamps des signatures

### Avantages
- ✅ Simple à comprendre et implémenter
- ✅ Évite le data leakage temporel
- ✅ Teste la généralisation sur le futur proche
- ✅ Rapide (pas de surcout de calcul)

### Inconvénients
- ⚠️ Un seul split : peut être sensible à des particularités du dernier 20%
- ⚠️ Pas de vue sur la stabilité du modèle sur différentes fenêtres temporelles

### Utilisation
```bash
git checkout feature/temporal-train-val-split
make start
make nilm-train
```

---

## Solution 2 : Time Series Cross-Validation

**Branche** : `feature/time-series-cross-validation`

### Principe
- Utilise `TimeSeriesSplit` de scikit-learn avec 5 folds
- Fenêtre glissante qui progresse dans le temps
- Le modèle final est entraîné sur le dernier fold (80% ancien / 20% récent)

### Comment ça marche

Avec 5 folds sur une timeline de 100 points :

```
Fold 1:  [Train: 0-20]    [Val: 20-40]
Fold 2:  [Train: 0-40]    [Val: 40-60]
Fold 3:  [Train: 0-60]    [Val: 60-80]
Fold 4:  [Train: 0-80]    [Val: 80-90]
Fold 5:  [Train: 0-80]    [Val: 90-100]  ← Utilisé pour le modèle final
```

### Avantages
- ✅ Plus robuste : teste la stabilité sur plusieurs fenêtres temporelles
- ✅ Évite le data leakage temporel
- ✅ Détecte si le modèle se dégrade dans le temps
- ✅ Conforme aux best practices académiques pour séries temporelles
- ✅ Peut être étendu pour calculer des métriques moyennes sur tous les folds

### Inconvénients
- ⚠️ Actuellement, seul le dernier fold est utilisé pour l'entraînement final
- ⚠️ Possibilité d'extension pour calculer les métriques sur tous les folds (pas implémenté)

### Utilisation
```bash
git checkout feature/time-series-cross-validation
make start
make nilm-train
```

---

## Recommandations

### Pour la production immédiate
➡️ **`feature/temporal-train-val-split`** (Solution 1)
- Plus simple et direct
- Déjà une amélioration majeure par rapport au split aléatoire
- Pas de complexité additionnelle

### Pour une validation plus robuste
➡️ **`feature/time-series-cross-validation`** (Solution 2)
- Meilleure garantie de généralisation
- Plus aligné avec les pratiques de recherche en ML sur séries temporelles
- Peut être étendu pour des analyses plus poussées

---

## Migration depuis `main`

Les deux branches sont **prêtes à merger** dans main. Choisissez l'une ou l'autre :

```bash
# Option 1 : Split simple
git checkout main
git merge feature/temporal-train-val-split

# Option 2 : Cross-validation
git checkout main
git merge feature/time-series-cross-validation
```

**Note** : Les deux solutions sont mutuellement exclusives. Il faut choisir l'une ou l'autre.

---

## Tests recommandés

Avant de merger en production :

1. **Entraîner un modèle** avec chaque approche
2. **Comparer les métriques de validation** (MAE, MSE)
3. **Tester en production** sur des données réelles
4. **Analyser les détections** pour vérifier la qualité

```bash
# Tester les deux approches
git checkout feature/temporal-train-val-split
make nilm-train
# Noter les métriques

git checkout feature/time-series-cross-validation
make nilm-train
# Comparer les métriques
```

---

## Références

- [Scikit-learn TimeSeriesSplit](https://scikit-learn.org/stable/modules/generated/sklearn.model_selection.TimeSeriesSplit.html)
- [Best practices for time series forecasting](https://machinelearningmastery.com/backtest-machine-learning-models-time-series-forecasting/)
