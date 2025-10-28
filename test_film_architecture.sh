#!/bin/bash

# Script de test pour l'architecture FiLM

echo "=========================================="
echo "🧪 Test Architecture NILM FiLM"
echo "=========================================="
echo ""

# 1. Vérifier l'architecture active
echo "1️⃣ Vérification architecture active..."
docker compose logs cnn-worker 2>/dev/null | grep "🎯 Architecture" | tail -1

if [ $? -eq 0 ]; then
    echo "   ✅ Architecture détectée"
else
    echo "   ❌ Impossible de détecter l'architecture"
    exit 1
fi

echo ""

# 2. Vérifier les services
echo "2️⃣ Vérification services..."
services=("cnn-worker" "cnn-beat" "backend" "timescaledb")

for service in "${services[@]}"; do
    status=$(docker compose ps $service --format json 2>/dev/null | jq -r '.[0].State' 2>/dev/null)
    if [ "$status" = "running" ]; then
        echo "   ✅ $service: running"
    else
        echo "   ❌ $service: $status"
    fi
done

echo ""

# 3. Tester l'API d'entraînement
echo "3️⃣ Test API entraînement (sans lancer réellement)..."
response=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/api/health 2>/dev/null)

if [ "$response" = "200" ]; then
    echo "   ✅ API backend accessible"
else
    echo "   ❌ API backend non accessible (code: $response)"
fi

echo ""

# 4. Vérifier la structure des modèles
echo "4️⃣ Vérification structure models/..."
if [ -d "models" ]; then
    echo "   📁 Dossier models/ existe"
    
    # Lister les modèles FiLM
    film_models=$(find models -name "*film*.keras" 2>/dev/null | wc -l)
    echo "   📊 Modèles FiLM trouvés: $film_models"
    
    # Lister les métadonnées
    metadata=$(find models -name "*.metadata.json" 2>/dev/null | wc -l)
    echo "   📋 Fichiers métadonnées: $metadata"
else
    echo "   ⚠️  Dossier models/ n'existe pas encore"
fi

echo ""

# 5. Afficher la configuration
echo "5️⃣ Configuration environnement..."
echo "   NILM_ARCHITECTURE: $(docker compose config | grep NILM_ARCHITECTURE | awk '{print $2}')"
echo "   NILM_MODEL_TYPE: $(docker compose config | grep NILM_MODEL_TYPE | awk '{print $2}')"

echo ""
echo "=========================================="
echo "✅ Tests terminés"
echo "=========================================="
echo ""
echo "Pour lancer un entraînement FiLM:"
echo "  curl -X POST http://localhost:8000/api/nilm/train"
echo ""
echo "Pour voir les logs en temps réel:"
echo "  docker compose logs -f cnn-worker"
echo ""
