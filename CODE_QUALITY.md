# Code Quality - Guide

## Commandes disponibles

### `make code-quality-check`

Vérifie la qualité du code Python dans tous les services sans modifier les fichiers.

**Outils utilisés :**
- **Flake8** : Détecte les erreurs de style, les imports inutilisés, les lignes trop longues, etc.
- **isort** : Vérifie que les imports sont correctement triés

**Exemple d'utilisation :**
```bash
make code-quality-check
```

**Sortie :**
- Liste des violations de style détectées par Flake8
- Différences d'imports détectées par isort
- Retourne toujours avec succès (|| true) pour ne pas bloquer le workflow

### `make code-quality-fix`

Corrige automatiquement les problèmes de qualité de code dans tous les services.

**Outils utilisés :**
- **isort** : Trie et organise automatiquement les imports
- **Black** : Formate le code selon le style Black (88 caractères/ligne)

**Exemple d'utilisation :**
```bash
make code-quality-fix
```

**Avertissement :**
⚠️ Cette commande **modifie les fichiers** ! Assurez-vous d'avoir committé vos changements avant de l'exécuter.

## Configuration

### Flake8 (`.flake8`)

Configuration située dans `/home/rsaikali/linkya/.flake8` :

- **Max line length** : 88 caractères (compatible avec Black)
- **Erreurs ignorées** :
  - `E203` : Espace avant ':' (conflit avec Black)
  - `W503` : Saut de ligne avant opérateur binaire (conflit avec Black)
  - `E501` : Ligne trop longue (géré par Black)
- **Exclusions** : `.venv`, `__pycache__`, `node_modules`, `frontend-service`

### isort (`pyproject.toml`)

Configuration située dans `/home/rsaikali/linkya/pyproject.toml` :

- **Profile** : "black" (compatible avec Black)
- **Line length** : 88 caractères
- **Multi-line output** : Vertical Hanging Indent
- **Sections** : FUTURE, STDLIB, THIRDPARTY, FIRSTPARTY, LOCALFOLDER

### Black

Configuration par défaut :
- **Line length** : 88 caractères
- **Target version** : Python 3.12+

## Workflow recommandé

### 1. Avant de committer

```bash
# Vérifier la qualité du code
make code-quality-check

# Si des problèmes sont détectés, les corriger automatiquement
make code-quality-fix

# Vérifier à nouveau
make code-quality-check

# Committer les changements
git add .
git commit -m "style: Apply code quality fixes"
```

### 2. Dans votre éditeur (VS Code)

Les fichiers de configuration sont automatiquement détectés par VS Code grâce à `.vscode/settings.json` :

- **Formatage automatique** au save (Black)
- **Organisation des imports** au save (isort)
- **Linting en temps réel** (Flake8)

### 3. CI/CD (future)

Ces commandes peuvent être intégrées dans un pipeline CI/CD :

```yaml
# .github/workflows/code-quality.yml (exemple)
- name: Check code quality
  run: make code-quality-check
```

## Services concernés

Les commandes s'appliquent à tous les services Python :

- ✅ `backend-service/src/`
- ✅ `sync-service/src/`
- ✅ `nilm-service/src/`

Le frontend JavaScript n'est pas concerné (utilise ESLint/Prettier séparément).

## Erreurs courantes

### Import inutilisé (F401)

```python
# ❌ Avant
import os
import sys

def hello():
    print("Hello")  # os et sys non utilisés
```

```python
# ✅ Après (Flake8 détecte, vous devez supprimer manuellement)
def hello():
    print("Hello")
```

### Imports mal triés

```python
# ❌ Avant
from fastapi import FastAPI
import os
from sqlalchemy import create_engine
import sys
```

```python
# ✅ Après (isort corrige automatiquement)
import os
import sys

from fastapi import FastAPI
from sqlalchemy import create_engine
```

### Formatage inconsistant

```python
# ❌ Avant
def calculate(a,b,c):
    result=a+b+c
    if result>100:
        return result
    else:
        return 0
```

```python
# ✅ Après (Black corrige automatiquement)
def calculate(a, b, c):
    result = a + b + c
    if result > 100:
        return result
    else:
        return 0
```

## Prérequis

Les outils doivent être installés dans les environnements virtuels :

```bash
# Installer/réinstaller les outils
make vscode-reinstall
```

Ou manuellement :
```bash
cd backend-service
source .venv/bin/activate
pip install black flake8 isort
```

## Intégration Git (optionnel)

Vous pouvez ajouter un pre-commit hook pour vérifier automatiquement :

```bash
# .git/hooks/pre-commit
#!/bin/bash
make code-quality-check
```

Ou utiliser le package `pre-commit` :

```bash
pip install pre-commit
pre-commit install
```

## Notes importantes

- ✅ **Black** est le formateur principal (référence)
- ✅ **isort** est configuré pour être compatible avec Black
- ✅ **Flake8** ignore les conflits avec Black (E203, W503, E501)
- ✅ Tous les outils utilisent **88 caractères** comme limite de ligne
- ⚠️ `code-quality-fix` modifie les fichiers en place
- ⚠️ Certaines erreurs Flake8 nécessitent une correction manuelle (ex: imports inutilisés)

## Ressources

- [Black documentation](https://black.readthedocs.io/)
- [Flake8 documentation](https://flake8.pycqa.org/)
- [isort documentation](https://pycqa.github.io/isort/)
- [PEP 8 - Style Guide for Python Code](https://www.python.org/dev/peps/pep-0008/)
