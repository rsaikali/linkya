#!/usr/bin/env python3
"""
Script de diagnostic pour vérifier les signatures NILM
Affiche les signatures trop courtes pour l'entraînement S2P
"""
import sys
import os

# Ajouter le path parent pour les imports
current_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(current_dir))

# Imports avec gestion d'erreur
try:
    from src.database import db_manager
    from src.config import settings
except ImportError:
    # Fallback si exécuté depuis /app/src
    from database import db_manager
    from config import settings

from sqlalchemy import text


def check_signatures():
    """Vérifie toutes les signatures et affiche les diagnostics"""
    
    min_length = settings.effective_sequence_length
    min_duration_minutes = min_length / 60
    
    print("=" * 80)
    print("🔍 DIAGNOSTIC DES SIGNATURES NILM S2P")
    print("=" * 80)
    print(f"\n📊 Configuration actuelle:")
    print(f"   - Fenêtre: {settings.cnn_window_size_minutes} minutes")
    print(f"   - Séquence: {min_length} points (à 1Hz)")
    print(f"   - Durée minimale requise: {min_duration_minutes:.1f} minutes\n")
    
    try:
        with db_manager.get_session() as session:
            # Récupérer toutes les signatures avec durée
            query = """
                SELECT 
                    s.id,
                    a.name as appliance_name,
                    s.start_time,
                    s.end_time,
                    EXTRACT(EPOCH FROM (s.end_time - s.start_time)) as duration_seconds,
                    (SELECT COUNT(*) 
                     FROM linky_realtime lr 
                     WHERE lr.time >= s.start_time 
                     AND lr.time <= s.end_time) as num_points
                FROM cnn_signatures s
                JOIN cnn_appliances a ON s.appliance_id = a.id
                ORDER BY a.name, s.start_time
            """
            
            result = session.execute(text(query))
            signatures = result.fetchall()
            
            if not signatures:
                print("❌ Aucune signature trouvée\n")
                return
            
            print(f"📝 {len(signatures)} signature(s) trouvée(s)\n")
            
            valid_count = 0
            short_count = 0
            no_data_count = 0
            
            by_appliance = {}
            
            for sig in signatures:
                sig_id = sig.id
                appliance = sig.appliance_name
                duration_minutes = sig.duration_seconds / 60 if sig.duration_seconds else 0
                num_points = sig.num_points or 0
                
                if appliance not in by_appliance:
                    by_appliance[appliance] = {
                        'valid': [],
                        'short': [],
                        'no_data': []
                    }
                
                status = ""
                if num_points == 0:
                    status = f"❌ AUCUNE DONNÉE"
                    by_appliance[appliance]['no_data'].append(sig_id)
                    no_data_count += 1
                elif num_points < min_length:
                    status = f"⚠️  TROP COURTE ({duration_minutes:.1f} min < {min_duration_minutes:.1f} min, {num_points} points)"
                    by_appliance[appliance]['short'].append(sig_id)
                    short_count += 1
                else:
                    status = f"✅ OK ({duration_minutes:.1f} min, {num_points} points)"
                    by_appliance[appliance]['valid'].append(sig_id)
                    valid_count += 1
                
                print(f"  Signature #{sig_id} - {appliance}: {status}")
            
            print("\n" + "=" * 80)
            print("📈 RÉSUMÉ PAR APPAREIL")
            print("=" * 80 + "\n")
            
            for appliance, stats in sorted(by_appliance.items()):
                total = len(stats['valid']) + len(stats['short']) + len(stats['no_data'])
                print(f"🔌 {appliance}:")
                print(f"   ✅ Valides: {len(stats['valid'])}/{total}")
                
                if stats['short']:
                    print(f"   ⚠️  Trop courtes: {len(stats['short'])} (IDs: {', '.join(map(str, stats['short']))})")
                
                if stats['no_data']:
                    print(f"   ❌ Sans données: {len(stats['no_data'])} (IDs: {', '.join(map(str, stats['no_data']))})")
                
                if len(stats['valid']) >= 2:
                    print(f"   ✅ PRÊT pour entraînement S2P")
                else:
                    print(f"   ⚠️  INSUFFISANT: besoin d'au moins 2 signatures valides (actuellement {len(stats['valid'])})")
                
                print()
            
            print("=" * 80)
            print("📊 RÉSUMÉ GLOBAL")
            print("=" * 80)
            print(f"Total signatures: {len(signatures)}")
            print(f"  ✅ Valides: {valid_count}")
            print(f"  ⚠️  Trop courtes: {short_count}")
            print(f"  ❌ Sans données: {no_data_count}")
            print()
            
            if short_count > 0 or no_data_count > 0:
                print("💡 RECOMMANDATIONS:")
                print()
                if short_count > 0:
                    print(f"   1. Créez des signatures d'au moins {min_duration_minutes:.1f} minutes")
                    print(f"      (actuellement: CNN_WINDOW_SIZE_MINUTES={settings.cnn_window_size_minutes})")
                    print()
                
                if no_data_count > 0:
                    print(f"   2. Vérifiez que les signatures ont des données dans linky_realtime")
                    print(f"      (période couverte, synchronisation active)")
                    print()
                
                print(f"   3. Option: Réduire CNN_WINDOW_SIZE_MINUTES dans .env")
                print(f"      (minimum recommandé: 5 minutes pour S2P)")
                print()
            
            if valid_count >= 2:
                print("✅ Vous pouvez lancer l'entraînement !")
                print("   Commande: make nilm-train ou make api-nilm-train")
            else:
                print("⚠️  Entraînement impossible: besoin d'au moins 2 signatures valides par appareil")
            
            print()
            
    except Exception as e:
        print(f"❌ Erreur: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    check_signatures()
