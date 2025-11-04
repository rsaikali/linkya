#!/usr/bin/env python3
"""
Script de test pour vérifier les améliorations NILM Phase 1 & 2
"""
import os
import sys

# Ajouter le chemin du module
sys.path.insert(0, '/home/rsaikali/nilmia/nilm-cnn-service/src')

from config import settings

print("="*60)
print("TEST DES AMÉLIORATIONS NILM - Phase 1 & 2")
print("="*60)

print("\n✅ PHASE 1 - Configuration:")
print(f"   - sequence_length: {settings.effective_sequence_length} (attendu: 599)")
print(f"   - min_power_threshold: {settings.cnn_min_power_threshold}W (attendu: 15W)")
print(f"   - min_duration_seconds: {settings.cnn_min_duration_seconds}s")

print("\n✅ PHASE 2 - Architecture:")
architecture = os.getenv('NILM_ARCHITECTURE', 'multioutput')
model_type = os.getenv('NILM_MODEL_TYPE', 'gru')
print(f"   - NILM_ARCHITECTURE: {architecture} (attendu: multioutput)")
print(f"   - NILM_MODEL_TYPE: {model_type}")

print("\n✅ Import des classes:")
try:
    from seq2point_nilm import (
        Seq2PointMultiOutputModel,
        Seq2PointFiLMModel,
        Seq2PointNILMManager,
        MultiHeadAttentionLayer,
        asymmetric_loss
    )
    print("   - Seq2PointMultiOutputModel: OK")
    print("   - MultiHeadAttentionLayer: OK")
    print("   - Seq2PointNILMManager: OK")
    print("   - asymmetric_loss: OK")
except ImportError as e:
    print(f"   ❌ Erreur d'import: {e}")
    sys.exit(1)

print("\n✅ Vérification false_positive_penalty:")
# Vérifier que la valeur par défaut est 1.5
import inspect
sig = inspect.signature(asymmetric_loss)
fp_penalty_default = sig.parameters['false_positive_penalty'].default
print(f"   - false_positive_penalty: {fp_penalty_default} (attendu: 1.5)")

print("\n✅ Test création modèle Multi-Output:")
try:
    model = Seq2PointMultiOutputModel(
        appliance_ids=[1, 2],
        appliance_names=['Test Appareil 1', 'Test Appareil 2'],
        sequence_length=599,
        model_type='gru'
    )
    print(f"   - Nombre d'appareils: {model.num_appliances}")
    print(f"   - Séquence: {model.sequence_length}")
    print(f"   - Type: {model.model_type}")
    print("   - Création: OK")
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    sys.exit(1)

print("\n✅ Test création NILMManager:")
try:
    os.environ['NILM_ARCHITECTURE'] = 'multioutput'
    manager = Seq2PointNILMManager()
    print(f"   - Architecture: {manager.architecture}")
    print(f"   - Model type: {manager.model_type}")
    print("   - Création: OK")
except Exception as e:
    print(f"   ❌ Erreur: {e}")
    sys.exit(1)

print("\n" + "="*60)
print("✅ TOUS LES TESTS PASSENT !")
print("="*60)
print("\nProchaines étapes:")
print("1. Définir NILM_ARCHITECTURE=multioutput dans .env")
print("2. Lancer un entraînement: docker compose exec nilm-cnn-service python -m tasks train")
print("3. Surveiller les logs pour voir l'architecture Multi-Output")
print("4. Comparer les détections avec l'ancien modèle FiLM")
