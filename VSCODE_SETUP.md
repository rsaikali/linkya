# Configuration VS Code - Guide rapide

## Installation en 3 étapes

### 1️⃣ Exécuter le script d'installation

```bash
./setup-vscode-env.sh
```

Ce script crée les environnements virtuels Python pour chaque service et installe toutes les dépendances.

**Prérequis :** Python 3.12 (obligatoire), Python 3.13 (recommandé)

### 2️⃣ Installer les extensions recommandées

Quand VS Code vous propose d'installer les extensions recommandées, cliquez sur **"Install All"**.

Ou manuellement : `Ctrl+Shift+X` > cherchez `@recommended`

### 3️⃣ Recharger VS Code

`Ctrl+Shift+P` > `Developer: Reload Window`

## ✅ C'est fait !

Vous devriez maintenant avoir :
- ✅ Coloration syntaxique complète
- ✅ IntelliSense fonctionnel
- ✅ Détection d'erreurs en temps réel
- ✅ Formatage automatique (Black pour Python, Prettier pour JS)
- ✅ Pas de soulignement rouge partout 🎉

## 🔍 Vérification

1. Ouvrez `backend-service/src/main.py`
2. En bas à droite, vérifiez que l'interpréteur Python est `('.venv': venv)`
3. Les imports FastAPI ne devraient plus être soulignés en rouge
4. L'autocomplétion devrait fonctionner

## 📚 Documentation complète

Voir `.vscode/README.md` pour plus de détails.

## ⚠️ Important

- Les `.venv` sont **uniquement pour VS Code** (IntelliSense, linting)
- Les services Docker utilisent **leurs propres environnements** (inchangé)
- Les `.venv` ne sont **pas committés** dans Git

## 🆘 Problème ?

Si les imports sont toujours soulignés :
1. `Ctrl+Shift+P` > `Python: Select Interpreter`
2. Choisissez `./backend-service/.venv/bin/python`
3. Rechargez la fenêtre
