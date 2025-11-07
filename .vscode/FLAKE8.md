# Flake8 dans VS Code

## Configuration

VS Code utilise automatiquement le fichier `.flake8` à la racine du projet grâce à cette configuration dans `.vscode/settings.json` :

```json
{
  "python.linting.flake8Enabled": true,
  "python.linting.flake8Args": [
    "--config=${workspaceFolder}/.flake8"
  ],
  "python.linting.lintOnSave": true
}
```

## Fonctionnement

### Automatique
- ✅ **Lint à chaque sauvegarde** : Les erreurs s'affichent automatiquement
- ✅ **Soulignement en temps réel** : Les erreurs sont soulignées dans l'éditeur
- ✅ **Panneau Problèmes** : `Ctrl+Shift+M` pour voir tous les problèmes

### Configuration centralisée
Le fichier `.flake8` à la racine contient :
- Max line length : 88 (compatible Black)
- Règles ignorées : E203, W503, E501 (conflits avec Black)
- Exclusions : `.venv`, `__pycache__`, `node_modules`

## Ignorer des erreurs

### Dans un fichier entier
```python
# flake8: noqa

import unused_module  # Ne génère pas d'erreur F401
```

### Sur une ligne spécifique
```python
import os  # noqa: F401  (import inutilisé mais volontaire)
```

### Sur une ligne (toutes les erreurs)
```python
long_line = "une très longue ligne qui dépasse 88 caractères..."  # noqa
```

## Codes d'erreurs courants

| Code | Description | Action |
|------|-------------|--------|
| **F401** | Import inutilisé | Supprimer l'import ou ajouter `# noqa: F401` |
| **F841** | Variable non utilisée | Utiliser la variable ou la supprimer |
| **F541** | f-string sans placeholder | Convertir en string normal : `f"text"` → `"text"` |
| **E226** | Espace manquant autour d'opérateur | Laisser Black corriger |
| **W291** | Espace en fin de ligne | `make code-quality-fix` supprime |

## Commandes utiles

### Voir les problèmes
```bash
# Dans VS Code
Ctrl+Shift+M  # Ouvrir le panneau Problèmes

# En ligne de commande
make code-quality-check
```

### Corriger automatiquement
```bash
make code-quality-fix  # Black + isort + trailing whitespace
```

### Voir les problèmes manuels
```bash
make code-quality-manual  # Uniquement F401, F841, F541
```

## Priorisation des erreurs

VS Code affiche les erreurs Flake8 par sévérité :
- 🔴 **Erreur** : Problèmes de syntaxe, imports invalides
- 🟡 **Avertissement** : Style, imports inutilisés
- 🔵 **Info** : Suggestions d'amélioration

## Désactiver temporairement

### Dans VS Code
1. Ouvrir la palette de commandes : `Ctrl+Shift+P`
2. Chercher "Python: Enable/Disable Linting"
3. Sélectionner "Disable"

### En configuration
Modifier `.vscode/settings.json` :
```json
{
  "python.linting.flake8Enabled": false
}
```

## Debugging de la configuration

### Vérifier que Flake8 utilise le bon config
```bash
backend-service/.venv/bin/flake8 --config=.flake8 backend-service/src/
```

### Voir la configuration active
```bash
backend-service/.venv/bin/flake8 --version
backend-service/.venv/bin/flake8 --show-source backend-service/src/config.py
```

## Intégration avec make

Les commandes Makefile utilisent aussi `.flake8` :
- `make code-quality-check` : Utilise Flake8 avec `.flake8`
- `make code-quality-fix` : N'utilise pas Flake8 (seulement Black + isort)
- `make code-quality-manual` : Filtre les erreurs Flake8

## Bonnes pratiques

1. **Toujours sauvegarder** pour déclencher le lint automatique
2. **Corriger en temps réel** plutôt qu'accumuler les erreurs
3. **Utiliser `# noqa` avec parcimonie** (seulement si vraiment nécessaire)
4. **Lancer `make code-quality-fix`** avant de committer
5. **Vérifier le panneau Problèmes** régulièrement

## Ressources

- [Flake8 documentation](https://flake8.pycqa.org/)
- [Liste complète des codes d'erreurs](https://flake8.pycqa.org/en/latest/user/error-codes.html)
- [VS Code Python linting](https://code.visualstudio.com/docs/python/linting)
