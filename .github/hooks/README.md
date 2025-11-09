# Git Hooks pour Linkya

## Installation

Pour installer le hook pre-commit qui formate automatiquement le code Python :

```bash
./setup-hooks.sh install
```

## Désinstallation

Pour désinstaller le hook :

```bash
./setup-hooks.sh uninstall
```

## Vérifier le statut

Pour vérifier quels hooks sont installés :

```bash
./setup-hooks.sh status
```

## Fonctionnement

Le hook **pre-commit** :
- Détecte tous les fichiers Python (`.py`) dans le commit
- Lance automatiquement `make code-quality-fix` pour formater le code
- Re-stage les fichiers modifiés
- Continue le commit normalement

### Ce que fait `make code-quality-fix`

1. **Black** : Formate le code Python selon PEP 8
2. **isort** : Trie et organise les imports
3. **Trailing whitespace** : Supprime les espaces en fin de ligne

## Exemple d'utilisation

```bash
# Modifier un fichier Python
vim backend-service/src/main.py

# Staging
git add backend-service/src/main.py

# Commit (le hook s'exécute automatiquement)
git commit -m "feat: add new feature"

# Sortie :
# 🔍 Running pre-commit code quality checks...
# 📝 Formatting staged Python files...
#   • backend-service/src/main.py
# Running: make code-quality-fix
# ✓ Code formatted successfully
# ✓ Changes re-staged
# ✓ Pre-commit checks passed
```

## Bypass du hook (si nécessaire)

Si vous devez commit sans exécuter le hook (déconseillé) :

```bash
git commit --no-verify -m "message"
```

## Désactiver temporairement

```bash
./setup-hooks.sh uninstall
# ... faire vos commits ...
./setup-hooks.sh install
```

## Prérequis

- Docker Compose doit être en cours d'exécution pour que `make code-quality-fix` fonctionne
- Les services backend, sync-worker, et nilm-worker doivent avoir Black et isort installés (déjà inclus dans les images)

## Avantages

✅ Code toujours formaté de manière cohérente
✅ Pas besoin de se souvenir d'exécuter `make code-quality-fix`
✅ Évite les commits de formatage séparés
✅ Garantit le respect des standards PEP 8

## Notes

- Le hook ne bloque jamais le commit (exit 0 même en cas d'erreur)
- Si `make code-quality-fix` échoue, un avertissement s'affiche mais le commit continue
- Les fichiers non-Python ne sont pas affectés
