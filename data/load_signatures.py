#!/usr/bin/env python3
"""
Script pour charger les signatures du Ballon d'Eau Chaude via l'API REST.

Ce script crée 10 signatures du ballon d'eau chaude en utilisant l'API
backend pour qu'elles suivent le chemin normal avec extraction des features.

Usage:
    python data/load_signatures.py
"""

import requests
import sys

# Configuration
API_BASE_URL = "http://localhost:8000"
APPLIANCE_NAME = "Ballon d'Eau Chaude"

# Liste des signatures à créer
SIGNATURES = [
    {
        "start_time": "2025-10-20T14:24:02+02:00",
        "end_time": "2025-10-20T14:50:32+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle après-midi normal (26.5 min, 3548W)"
    },
    {
        "start_time": "2025-10-20T15:00:31+02:00",
        "end_time": "2025-10-20T15:04:25+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Micro-cycle appoint très court (3.9 min, 3508W)"
    },
    {
        "start_time": "2025-10-20T23:54:02+02:00",
        "end_time": "2025-10-21T00:10:41+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle court nocturne (16.7 min, 3286W)"
    },
    {
        "start_time": "2025-10-21T14:24:02+02:00",
        "end_time": "2025-10-21T14:50:19+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle après-midi normal (26.3 min, 3580W)"
    },
    {
        "start_time": "2025-10-21T15:16:22+02:00",
        "end_time": "2025-10-21T15:22:15+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Micro-cycle appoint (5.9 min, 3534W)"
    },
    {
        "start_time": "2025-10-21T23:54:02+02:00",
        "end_time": "2025-10-22T00:10:04+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle court nocturne (16.0 min, 3346W)"
    },
    {
        "start_time": "2025-10-22T04:36:04+02:00",
        "end_time": "2025-10-22T04:45:38+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle matinal de maintien (9.6 min, 3216W)"
    },
    {
        "start_time": "2025-10-22T14:24:01+02:00",
        "end_time": "2025-10-22T14:36:45+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle rapide (12.7 min, 3498W)"
    },
    {
        "start_time": "2025-10-22T23:54:03+02:00",
        "end_time": "2025-10-23T00:08:46+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle court nocturne (14.7 min, 3261W)"
    },
    {
        "start_time": "2025-10-20T14:24:02+02:00",
        "end_time": "2025-10-20T15:04:25+02:00",
        "appliance_name": APPLIANCE_NAME,
        "description": "Cycle prolongé haute puissance (40.4 min, 3543W)"
    },
]


def check_api_health():
    """Vérifie que l'API est accessible."""
    try:
        response = requests.get(f"{API_BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print("✓ API backend accessible")
            return True
        else:
            print(f"✗ API backend retourne un code {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Impossible de contacter l'API: {e}")
        print("  Assurez-vous que le backend est démarré")
        print("  (docker compose up -d)")
        return False


def get_all_appliances():
    """Récupère tous les appareils existants."""
    try:
        response = requests.get(f"{API_BASE_URL}/api/appliances", timeout=5)
        if response.status_code == 200:
            data = response.json()
            # L'API retourne {"total": X, "appliances": [...]}
            return data.get("appliances", [])
        return []
    except requests.exceptions.RequestException:
        return []


def delete_appliance(appliance_id):
    """Supprime un appareil et toutes ses signatures."""
    try:
        response = requests.delete(
            f"{API_BASE_URL}/api/appliances/{appliance_id}",
            timeout=10
        )
        return response.status_code in [200, 204]
    except requests.exceptions.RequestException:
        return False


def cleanup_existing_data():
    """Supprime tous les appareils et signatures existants."""
    print("Nettoyage des données existantes...")
    
    appliances = get_all_appliances()
    if not appliances:
        print("  Aucune donnée existante à supprimer")
        return True
    
    print(f"  Suppression de {len(appliances)} appareil(s)...")
    success_count = 0
    
    for appliance in appliances:
        appliance_id = appliance.get("id")
        appliance_name = appliance.get("name", "Inconnu")
        
        if delete_appliance(appliance_id):
            print(f"    ✓ {appliance_name} (ID: {appliance_id}) supprimé")
            success_count += 1
        else:
            print(f"    ✗ Échec: {appliance_name} (ID: {appliance_id})")
    
    print(f"  {success_count}/{len(appliances)} appareil(s) supprimé(s)")
    print()
    return True


def create_signature(signature_data):
    """Crée une signature via l'API."""
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/signatures",
            json=signature_data,
            timeout=30
        )
        
        if response.status_code in [200, 201]:
            data = response.json()
            return True, data
        else:
            # Essayer de récupérer le détail de l'erreur
            try:
                error_data = response.json()
                error_msg = error_data.get(
                    "detail",
                    f"HTTP {response.status_code}"
                )
            except ValueError:
                error_msg = (
                    f"HTTP {response.status_code}: "
                    f"{response.text[:100]}"
                )
            return False, error_msg
            
    except requests.exceptions.RequestException as e:
        return False, str(e)


def main():
    """Fonction principale."""
    print("=" * 70)
    print("Chargement des signatures du Ballon d'Eau Chaude")
    print("=" * 70)
    print()
    
    # Vérifier l'API
    if not check_api_health():
        sys.exit(1)
    
    print()
    
    # Nettoyer les données existantes
    cleanup_existing_data()
    
    print(f"Création de {len(SIGNATURES)} signatures...")
    print()
    
    success_count = 0
    error_count = 0
    
    for i, signature in enumerate(SIGNATURES, 1):
        print(f"[{i}/{len(SIGNATURES)}] {signature['description']}")
        print(f"        {signature['start_time']} → {signature['end_time']}")

        success, result = create_signature(signature)
        
        if success:
            print(f"        ✓ Signature créée (ID: {result.get('id', 'N/A')})")
            success_count += 1
        else:
            print(f"        ✗ Erreur: {result}")
            error_count += 1
        
        print()

    # Résumé
    print("=" * 70)
    print("Résumé")
    print("=" * 70)
    print(f"✓ Signatures créées: {success_count}/{len(SIGNATURES)}")
    if error_count > 0:
        print(f"✗ Erreurs: {error_count}")
    print()

    print("Les features ont été extraites automatiquement par le service CNN.")
    print("Vous pouvez maintenant entraîner le modèle avec: make nilm-train")
    print("=" * 70)
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
