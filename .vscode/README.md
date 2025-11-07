# Configuration VS Code pour Linkya

Ce répertoire contient la configuration VS Code optimisée pour le développement multi-services de Linkya.

## 🎯 Objectif

Permettre une expérience de développement fluide avec :
- ✅ Coloration syntaxique complète pour Python et JavaScript
- ✅ IntelliSense et autocomplétion fonctionnels
- ✅ Détection des erreurs en temps réel
- ✅ Support du debugging
- ✅ Formatage automatique du code

## 📦 Configuration

### Fichiers inclus

- **`settings.json`** : Configuration globale du workspace
  - Chemins Python pour chaque service
  - Formatage automatique (Black pour Python, Prettier pour JS)
  - Linting avec Flake8
  - Exclusions de fichiers optimisées

- **`extensions.json`** : Extensions recommandées
  - Python (Pylance, Black, Flake8, Debugpy)
  - ESLint et Prettier pour JavaScript/React
  - Docker support

## 🚀 Installation

### 1. Exécuter le script de configuration

À la racine du projet :

```bash
./setup-vscode-env.sh
```

Ce script va :
- Créer un environnement virtuel `.venv` dans chaque service Python
- Installer toutes les dépendances du projet
- Installer les outils de développement (black, flake8, pytest)

**Prérequis :**
- Python 3.12 installé (obligatoire)
- Python 3.13 installé (recommandé, sinon utilise 3.12 pour sync-service)

### 2. Installer les extensions recommandées

Quand vous ouvrez le projet dans VS Code :
1. Une notification apparaît proposant d'installer les extensions recommandées
2. Cliquez sur "Install All"

Ou manuellement :
- `Ctrl+Shift+X` pour ouvrir les Extensions
- Recherchez `@recommended` pour voir les extensions recommandées

### 3. Recharger VS Code

`Ctrl+Shift+P` > `Developer: Reload Window`

## ✅ Vérification

### Interpréteur Python

1. Ouvrez un fichier Python (ex: `backend-service/src/main.py`)
2. Vérifiez en bas à droite de VS Code que l'interpréteur est : `('.venv': venv)`
3. Si non, sélectionnez-le manuellement :
   - `Ctrl+Shift+P` > `Python: Select Interpreter`
   - Choisissez `./backend-service/.venv/bin/python`

### IntelliSense

1. Ouvrez `backend-service/src/main.py`
2. Tapez `from fastapi import ` et vérifiez que l'autocomplétion fonctionne
3. Survolez une fonction importée pour voir sa documentation

### Linting

1. Ouvrez un fichier Python
2. Les erreurs de syntaxe devraient apparaître immédiatement
3. Les avertissements Flake8 s'affichent en jaune

## 🔧 Environnements virtuels

### Structure

Chaque service Python a son propre `.venv` :

```
backend-service/
├── .venv/          # Python 3.12 + pip
└── src/

sync-service/
├── .venv/          # Python 3.13 + uv
└── src/

nilm-service/
├── .venv/          # Python 3.12 + uv
└── src/
```

### Pourquoi des .venv locaux ?

- Les services tournent dans Docker avec leurs propres environnements
- VS Code a besoin des packages installés localement pour l'IntelliSense
- Les `.venv` ne sont **PAS** utilisés en production, seulement pour le développement

### Gestion manuelle

Si vous modifiez les dépendances d'un service :

```bash
# Backend (pip)
cd backend-service
source .venv/bin/activate
pip install -r requirements.txt
deactivate

# Sync ou NILM (uv)
cd sync-service  # ou nilm-service
source .venv/bin/activate
uv pip install --system -r pyproject.toml
deactivate
```

Ou relancez simplement `./setup-vscode-env.sh`

## 🎨 Formatage automatique

### Python (Black)

- Format au save activé automatiquement
- Norme : 88 caractères par ligne
- Compatible PEP 8

### JavaScript/React (Prettier)

- Format au save activé
- Configuration dans `frontend-service/.prettierrc` (si existe)

### Linting

- `Shift+Alt+O` : Organise les imports Python
- Automatique au save si configuré

#### Flake8

Flake8 est configuré pour utiliser le fichier `.flake8` à la racine du projet :
- Lint automatique à chaque sauvegarde (`lintOnSave: true`)
- Configuration centralisée dans `.flake8`
- Compatible avec Black (88 caractères, ignore E203, W503, E501)
- Les erreurs s'affichent en temps réel dans VS Code

Pour désactiver temporairement une règle dans un fichier :
```python
# flake8: noqa
```

Pour désactiver une règle sur une ligne :
```python
import os  # noqa: F401
```

## 🐛 Debugging

La configuration de debugging peut être ajoutée dans `.vscode/launch.json` si nécessaire.

Pour l'instant, utilisez le debugging Docker directement ou ajoutez des breakpoints dans le code.

## ⚠️ Notes importantes

### .gitignore

- Les `.venv/` sont ignorés (pas committés)
- Les fichiers `.vscode/settings.json` et `.vscode/extensions.json` sont **committés**
- Cela permet à toute l'équipe d'avoir la même configuration

### Performances

Si VS Code est lent :
1. Vérifiez que `files.watcherExclude` inclut `.venv` (déjà configuré)
2. Fermez les onglets inutilisés
3. Désactivez temporairement les extensions non essentielles

### Multi-root workspace

Cette configuration fonctionne avec un workspace mono-racine.

Si vous préférez un workspace multi-racines, utilisez `linkya.code-workspace` (voir documentation principale).

## 📚 Ressources

- [Documentation VS Code Python](https://code.visualstudio.com/docs/languages/python)
- [Pylance](https://github.com/microsoft/pylance-release)
- [Black formatter](https://black.readthedocs.io/)
- [Flake8](https://flake8.pycqa.org/)

## 🆘 Problèmes courants

### "Import X could not be resolved"

1. Vérifiez que le `.venv` du service existe
2. Relancez `./setup-vscode-env.sh`
3. Rechargez VS Code (`Ctrl+Shift+P` > `Reload Window`)
4. Sélectionnez manuellement l'interpréteur Python

### Les erreurs ne s'affichent pas

1. Vérifiez que Pylance est activé
2. Ouvrez la palette : `Ctrl+Shift+P` > `Python: Restart Language Server`

### Le formatage ne fonctionne pas

1. Vérifiez que Black est installé dans le `.venv`
2. Dans le `.venv` : `pip install black`
3. Rechargez VS Code
