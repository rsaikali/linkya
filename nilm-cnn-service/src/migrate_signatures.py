"""
Script de migration pour backfill les colonnes power_data et morphology_analysis
des signatures existantes.

Ce script:
1. Ajoute les nouvelles colonnes à la table cnn_signatures
2. Pour chaque signature existante, récupère les données de linky_realtime
3. Calcule power_data et morphology_analysis
4. Met à jour la signature
"""
import logging
import json
import numpy as np
from sqlalchemy import text

from .config import settings  # noqa: F401
from .database import db_manager
from .morphology import MorphologyAnalyzer

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def add_columns_if_not_exist():
    """Ajoute les nouvelles colonnes si elles n'existent pas."""
    logger.info("Vérification des colonnes de la table cnn_signatures...")
    
    with db_manager.engine.connect() as conn:
        # Check if columns exist
        check_query = text("""
            SELECT column_name
            FROM information_schema.columns
            WHERE table_name = 'cnn_signatures'
            AND column_name IN (
                'power_data',
                'avg_power',
                'power_std',
                'energy_consumed',
                'num_points',
                'morphology_analysis'
            )
        """)
        
        result = conn.execute(check_query)
        existing_cols = {row[0] for row in result}
        
        # Add missing columns
        if 'power_data' not in existing_cols:
            logger.info("Ajout colonne power_data...")
            conn.execute(text("""
                ALTER TABLE cnn_signatures
                ADD COLUMN power_data JSON
            """))
            conn.commit()
        
        if 'avg_power' not in existing_cols:
            logger.info("Ajout colonne avg_power...")
            conn.execute(text("""
                ALTER TABLE cnn_signatures
                ADD COLUMN avg_power FLOAT
            """))
            conn.commit()
        
        if 'power_std' not in existing_cols:
            logger.info("Ajout colonne power_std...")
            conn.execute(text("""
                ALTER TABLE cnn_signatures
                ADD COLUMN power_std FLOAT
            """))
            conn.commit()
        
        if 'energy_consumed' not in existing_cols:
            logger.info("Ajout colonne energy_consumed...")
            conn.execute(text("""
                ALTER TABLE cnn_signatures
                ADD COLUMN energy_consumed FLOAT
            """))
            conn.commit()
        
        if 'num_points' not in existing_cols:
            logger.info("Ajout colonne num_points...")
            conn.execute(text("""
                ALTER TABLE cnn_signatures
                ADD COLUMN num_points INTEGER
            """))
            conn.commit()
        
        if 'morphology_analysis' not in existing_cols:
            logger.info("Ajout colonne morphology_analysis...")
            conn.execute(text("""
                ALTER TABLE cnn_signatures
                ADD COLUMN morphology_analysis JSON
            """))
            conn.commit()
        
        logger.info("Colonnes vérifiées/ajoutées avec succès")


def backfill_signatures():
    """Backfill power_data et morphology_analysis pour signatures existantes."""
    logger.info("Début du backfill des signatures...")
    
    # Get all signatures without power_data
    with db_manager.engine.connect() as conn:
        query = text("""
            SELECT id, appliance_id, start_time, end_time, is_negative
            FROM cnn_signatures
            WHERE power_data IS NULL
            ORDER BY id
        """)
        
        signatures = conn.execute(query).fetchall()
        logger.info(f"Trouvé {len(signatures)} signatures à traiter")
    
    analyzer = MorphologyAnalyzer(sampling_rate_hz=1.0)
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for sig in signatures:
        sig_id = sig[0]
        appliance_id = sig[1]
        start_time = sig[2]
        end_time = sig[3]
        is_negative = sig[4]
        
        try:
            logger.info(f"Traitement signature {sig_id}...")
            
            # Get consumption data from linky_realtime
            consumption_data = db_manager.get_consumption_data(
                start_time,
                end_time
            )
            
            if not consumption_data:
                logger.warning(
                    f"Signature {sig_id}: aucune donnée dans linky_realtime "
                    f"(période: {start_time} - {end_time})"
                )
                skip_count += 1
                continue
            
            # Extract power values
            power_values = np.array([d['papp'] for d in consumption_data])
            
            # Build power_data
            power_data = {
                'start': start_time.isoformat(),
                'rate_hz': 1.0,
                'values': power_values.tolist(),
                'num_points': len(power_values),
            }
            
            # Compute stats
            avg_power = float(np.mean(power_values))
            power_std = float(np.std(power_values))
            energy_consumed = float(np.sum(power_values) / 3600.0)
            num_points = len(power_values)
            
            # Compute morphology (only for positive signatures)
            morphology_analysis = None
            if not is_negative and len(power_values) >= 10:
                morphology_analysis = analyzer.analyze(
                    power_values,
                    start_time
                )
            
            # Update signature
            with db_manager.engine.connect() as conn:
                update_query = text("""
                    UPDATE cnn_signatures
                    SET
                        power_data = :power_data,
                        avg_power = :avg_power,
                        power_std = :power_std,
                        energy_consumed = :energy_consumed,
                        num_points = :num_points,
                        morphology_analysis = :morphology_analysis
                    WHERE id = :sig_id
                """)
                
                conn.execute(
                    update_query,
                    {
                        'sig_id': sig_id,
                        'power_data': json.dumps(power_data),
                        'avg_power': avg_power,
                        'power_std': power_std,
                        'energy_consumed': energy_consumed,
                        'num_points': num_points,
                        'morphology_analysis': json.dumps(
                            morphology_analysis
                        ) if morphology_analysis else None,
                    }
                )
                conn.commit()
            
            logger.info(
                f"Signature {sig_id} mise à jour: "
                f"{num_points} points, {avg_power:.1f}W avg, "
                f"morphology={'computed' if morphology_analysis else 'skipped'}"
            )
            success_count += 1
            
        except Exception as e:
            logger.error(f"Erreur signature {sig_id}: {e}")
            error_count += 1
    
    logger.info(
        f"Backfill terminé: {success_count} OK, "
        f"{skip_count} ignorées (pas de données), "
        f"{error_count} erreurs"
    )


def main():
    """Point d'entrée du script de migration."""
    logger.info("=" * 60)
    logger.info("MIGRATION: Ajout power_data et morphology_analysis")
    logger.info("=" * 60)
    
    try:
        # Step 1: Add columns
        add_columns_if_not_exist()
        
        # Step 2: Backfill data
        backfill_signatures()
        
        logger.info("=" * 60)
        logger.info("MIGRATION TERMINÉE AVEC SUCCÈS")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"ERREUR CRITIQUE LORS DE LA MIGRATION: {e}")
        raise


if __name__ == '__main__':
    main()
