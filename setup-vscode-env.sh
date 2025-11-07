#!/bin/bash
set -e

echo "🔧 Configuration des environnements virtuels Python pour VS Code"
echo "================================================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to create venv
create_venv() {
    local service=$1
    local python_version=$2
    local use_uv=$3
    
    echo -e "${BLUE}📦 Configuration de ${service}...${NC}"
    cd "${service}"
    
    # Check if .venv already exists
    if [ -d ".venv" ]; then
        echo "  ⚠️  .venv existe déjà, suppression..."
        rm -rf .venv
    fi
    
    # Create virtual environment
    echo "  ✓ Création de l'environnement virtuel avec Python ${python_version}"
    ${python_version} -m venv --without-pip .venv
    
    # Activate and install pip manually
    source .venv/bin/activate
    echo "  ✓ Installation de pip"
    curl -sS https://bootstrap.pypa.io/get-pip.py | python
    
    if [ "$use_uv" = true ]; then
        echo "  ✓ Installation de uv"
        pip install --quiet uv
        echo "  ✓ Installation des dépendances via uv"
        uv pip install --system -r pyproject.toml
    else
        echo "  ✓ Installation des dépendances via pip"
        pip install --quiet -r requirements.txt
    fi
    
    # Install dev tools
    echo "  ✓ Installation des outils de développement"
    pip install --quiet black flake8 pytest
    
    deactivate
    cd ..
    echo -e "${GREEN}  ✅ ${service} configuré${NC}"
    echo ""
}

# Check Python versions - use system Python to avoid uv/pyenv issues
if [ -x "/usr/bin/python3.12" ]; then
    BACKEND_PYTHON="/usr/bin/python3.12"
    NILM_PYTHON="/usr/bin/python3.12"
else
    echo "❌ Python 3.12 n'est pas installé dans /usr/bin/"
    echo "   Installation requise pour backend-service et nilm-service"
    exit 1
fi

if [ -x "/usr/bin/python3.13" ]; then
    SYNC_PYTHON="/usr/bin/python3.13"
else
    echo "⚠️  Python 3.13 n'est pas installé"
    echo "   Utilisation de python3.12 pour sync-service"
    SYNC_PYTHON="/usr/bin/python3.12"
fi

# Create venvs for each service
create_venv "backend-service" "$BACKEND_PYTHON" false
create_venv "sync-service" "$SYNC_PYTHON" true
create_venv "nilm-service" "$NILM_PYTHON" true

echo -e "${GREEN}✅ Configuration terminée !${NC}"
echo ""
echo "📝 Prochaines étapes :"
echo "  1. Rechargez la fenêtre VS Code (Ctrl+Shift+P > 'Developer: Reload Window')"
echo "  2. VS Code devrait automatiquement détecter les environnements virtuels"
echo "  3. Vérifiez l'interpréteur Python en bas à droite de VS Code"
echo "  4. Si nécessaire, sélectionnez manuellement l'interpréteur :"
echo "     - Ctrl+Shift+P > 'Python: Select Interpreter'"
echo "     - Choisissez './backend-service/.venv/bin/python'"
echo ""
echo "💡 Les .venv sont ajoutés au .gitignore et ne seront pas committés"
