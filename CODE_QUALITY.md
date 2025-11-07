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
- **sed** : Supprime les espaces en fin de ligne (trailing whitespace)

**Exemple d'utilisation :**
```bash
make code-quality-fix
```

**Ce qui est corrigé automatiquement :**
- ✅ Ordre des imports (isort)
- ✅ Formatage du code (Black)
- ✅ Espaces en fin de ligne (sed)
- ✅ Indentation
- ✅ Espacement autour des opérateurs (la plupart)

**Avertissement :**
⚠️ Cette commande **modifie les fichiers** ! Assurez-vous d'avoir committé vos changements avant de l'exécuter.

### `make code-quality-manual` ⭐ NOUVEAU

Affiche uniquement les problèmes qui nécessitent une correction manuelle, classés par catégorie.

**Catégories d'erreurs :**
- **F401** : Imports inutilisés (à supprimer)
- **F841** : Variables assignées mais jamais utilisées (à supprimer ou utiliser)
- **F541** : f-strings sans placeholders (à convertir en strings normaux)

**Exemple d'utilisation :**
```bash
make code-quality-manual
```

**Sortie :**
```
⚠️  Issues requiring manual fixes:

🔍 Unused imports (F401):
backend-service/src/config.py:3:1: F401 'os' imported but unused

🔍 Unused variables (F841):
nilm-service/src/database.py:331:13: F841 local variable 'timestamps' is assigned to but never used

🔍 f-strings without placeholders (F541):
sync-service/src/database.py:202:34: F541 f-string is missing placeholders
```

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

# Si des problèmes sont détectés, corriger automatiquement ce qui peut l'être
make code-quality-fix

# Voir les problèmes restants qui nécessitent une intervention manuelle
make code-quality-manual

# Corriger manuellement les imports inutilisés, variables non utilisées, etc.
# (éditer les fichiers listés)

# Vérifier à nouveau
make code-quality-check

# Committer les changements
git add .
git commit -m "style: Apply code quality fixes"
```

### 2. Workflow rapide (auto-fix uniquement)

```bash
# Corriger automatiquement
make code-quality-fix

# Vérifier le résultat
make code-quality-check

# Committer (même s'il reste des warnings manuels)
git add .
git commit -m "style: Auto-format code with Black and isort"
```

### 3. Workflow complet (zéro erreur)

```bash
# 1. Auto-fix
make code-quality-fix

# 2. Identifier les problèmes manuels
make code-quality-manual

# 3. Corriger manuellement
# - Supprimer les imports inutilisés
# - Supprimer ou utiliser les variables non utilisées
# - Convertir f"text" en "text" si pas de placeholders

# 4. Vérifier qu'il n'y a plus d'erreurs
make code-quality-check
# Doit afficher "✓ Code quality check completed!" sans erreurs

# 5. Committer
git add .
git commit -m "style: Fix all code quality issues"
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
