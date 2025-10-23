"""Gestion de la base de données TimescaleDB."""

from datetime import datetime
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from .config import settings


def format_datetime_utc(dt: datetime | None) -> str | None:
    """
    Formate un datetime en ISO string avec timezone UTC explicite.
    
    Args:
        dt: Datetime à formater (naive, supposé UTC)
        
    Returns:
        String ISO avec suffixe 'Z' ou None
    """
    if dt is None:
        return None
    return dt.isoformat() + 'Z'


class DatabaseManager:
    """Gestionnaire de connexion à TimescaleDB."""

    def __init__(self):
        """Initialise la connexion à TimescaleDB."""
        self.engine = create_engine(
            settings.local_db_url,
            pool_pre_ping=True,
            pool_size=10,
            max_overflow=20,
        )
        self.SessionLocal = sessionmaker(
            autocommit=False, autoflush=False, bind=self.engine
        )

    def get_latest_consumption(self) -> dict[str, Any] | None:
        """Récupère la dernière valeur de consommation."""
        query = text("""
            SELECT time, papp, hchp, hchc, temperature, libelle_tarif
            FROM linky_realtime
            ORDER BY time DESC
            LIMIT 1
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if result:
                return {
                    "time": format_datetime_utc(result[0]),
                    "papp": result[1],
                    "hchp": result[2],
                    "hchc": result[3],
                    "temperature": result[4],
                    "libelle_tarif": result[5],
                }
            return None

    def get_consumption_history(
        self, start_time: datetime, end_time: datetime, interval: str = "5 minutes"
    ) -> list[dict[str, Any]]:
        """
        Récupère l'historique de consommation sur une période.

        Args:
            start_time: Date de début
            end_time: Date de fin
            interval: Intervalle d'agrégation (ex: '5 minutes', '1 hour', 'raw' pour données brutes)

        Returns:
            Liste des points de consommation agrégés ou bruts
        """
        # Si interval est "raw" ou "none", retourner les données brutes sans agrégation
        if interval in ("raw", "none"):
            query = text("""
                SELECT
                    time,
                    papp as avg_papp,
                    papp as max_papp,
                    papp as min_papp,
                    temperature as avg_temperature
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                ORDER BY time ASC
            """)
        else:
            query = text("""
                SELECT
                    time_bucket(:interval, time) AS bucket,
                    AVG(papp) as avg_papp,
                    MAX(papp) as max_papp,
                    MIN(papp) as min_papp,
                    AVG(temperature) as avg_temperature
                FROM linky_realtime
                WHERE time >= :start_time AND time <= :end_time
                GROUP BY bucket
                ORDER BY bucket ASC
            """)

        with self.engine.connect() as conn:
            if interval in ("raw", "none"):
                result = conn.execute(
                    query,
                    {
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
            else:
                result = conn.execute(
                    query,
                    {
                        "interval": interval,
                        "start_time": start_time,
                        "end_time": end_time,
                    },
                )
            return [
                {
                    "time": format_datetime_utc(row[0]),
                    "avg_papp": float(row[1]) if row[1] is not None else None,
                    "max_papp": float(row[2]) if row[2] is not None else None,
                    "min_papp": float(row[3]) if row[3] is not None else None,
                    "avg_temperature": float(row[4]) if row[4] is not None else None,
                }
                for row in result
            ]

    def get_detected_appliances(
        self, start_time: datetime | None = None, end_time: datetime | None = None
    ) -> list[dict[str, Any]]:
        """
        Récupère les appareils détectés par le NILM-CNN.

        Args:
            start_time: Filtre optionnel sur date de début
            end_time: Filtre optionnel sur date de fin

        Returns:
            Liste des détections avec informations sur les appareils
        """
        query = text("""
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                ca.description,
                cd.start_time,
                cd.end_time,
                cd.avg_power,
                cd.energy_consumed,
                cd.confidence_score,
                cd.prediction_class,
                cd.signature_id,
                cd.created_at
            FROM cnn_detections cd
            JOIN cnn_appliances ca ON cd.appliance_id = ca.id
            WHERE (:start_time IS NULL OR cd.start_time >= :start_time)
              AND (:end_time IS NULL OR cd.end_time <= :end_time)
            ORDER BY cd.start_time DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                query, {"start_time": start_time, "end_time": end_time}
            )
            return [
                {
                    "id": row[0],
                    "appliance_id": row[1],
                    "name": row[2],
                    "description": row[3],
                    "start_time": format_datetime_utc(row[4]),
                    "end_time": format_datetime_utc(row[5]),
                    "avg_power": float(row[6]) if row[6] is not None else None,
                    "energy_consumed": (
                        float(row[7]) if row[7] is not None else None
                    ),
                    "confidence_score": (
                        float(row[8]) if row[8] is not None else None
                    ),
                    "prediction_class": (
                        int(row[9]) if row[9] is not None else None
                    ),
                    "signature_id": (
                        int(row[10]) if row[10] is not None else None
                    ),
                    "created_at": format_datetime_utc(row[11]),
                }
                for row in result
            ]

    def get_all_appliances(self) -> list[dict[str, Any]]:
        """Récupère la liste de tous les appareils connus avec leurs statistiques CNN calculées à la volée."""
        query = text("""
            SELECT
                ca.id,
                ca.name,
                ca.description,
                ca.created_at,
                ca.updated_at,
                -- Statistiques calculées depuis les signatures
                AVG(cs.avg_power) as avg_power,
                STDDEV(cs.avg_power) as power_std,
                AVG(EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))) as avg_duration,
                COUNT(DISTINCT cs.id) as num_signatures,
                MAX(cs.start_time) as last_signature_start,
                MAX(cs.end_time) as last_signature_end,
                COUNT(DISTINCT cd.id) as detection_count
            FROM cnn_appliances ca
            LEFT JOIN cnn_signatures cs ON ca.id = cs.appliance_id
            LEFT JOIN cnn_detections cd ON ca.id = cd.appliance_id
            GROUP BY ca.id, ca.name, ca.description, ca.created_at, ca.updated_at
            ORDER BY ca.name ASC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query)
            appliances_list = []
            for row in result:
                appliance = {
                    "id": row[0],
                    "name": row[1],
                    "description": row[2],
                    "created_at": format_datetime_utc(row[3]),
                    "updated_at": format_datetime_utc(row[4]),
                    "avg_power": float(row[5]) if row[5] is not None else None,
                    "power_std": float(row[6]) if row[6] is not None else None,
                    "avg_duration": float(row[7]) if row[7] is not None else None,
                    "num_signatures": int(row[8]) if row[8] is not None else 0,
                    "last_signature_start": format_datetime_utc(row[9]),
                    "last_signature_end": format_datetime_utc(row[10]),
                    "signature_count": int(row[8]) if row[8] is not None else 0,  # Même que num_signatures
                    "detection_count": int(row[11]) if row[11] is not None else 0,
                }
                
                appliances_list.append(appliance)
            
            return appliances_list

    def get_appliance_signatures(
        self, appliance_id: int
    ) -> list[dict[str, Any]]:
        """
        Récupère toutes les signatures d'un appareil spécifique.

        Args:
            appliance_id: ID de l'appareil

        Returns:
            Liste des signatures avec leurs détails
        """
        query = text("""
            SELECT
                cs.id,
                cs.appliance_id,
                cs.start_time,
                cs.end_time,
                cs.avg_power,
                cs.power_std,
                cs.energy_consumed,
                cs.created_at,
                EXTRACT(EPOCH FROM (cs.end_time - cs.start_time))
                    as duration_seconds
            FROM cnn_signatures cs
            WHERE cs.appliance_id = :appliance_id
            ORDER BY cs.start_time DESC
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query, {"appliance_id": appliance_id})
            signatures_list = []
            for row in result:
                signature = {
                    "id": row[0],
                    "appliance_id": row[1],
                    "start_time": format_datetime_utc(row[2]),
                    "end_time": format_datetime_utc(row[3]),
                    "avg_power": (
                        float(row[4]) if row[4] is not None else None
                    ),
                    "power_std": (
                        float(row[5]) if row[5] is not None else None
                    ),
                    "energy_consumed": (
                        float(row[6]) if row[6] is not None else None
                    ),
                    "created_at": format_datetime_utc(row[7]),
                    "duration_seconds": (
                        float(row[8]) if row[8] is not None else None
                    ),
                }
                signatures_list.append(signature)
            
            return signatures_list

    def update_appliance(
        self,
        appliance_id: int,
        name: str | None = None,
        description: str | None = None
    ) -> dict[str, Any] | None:
        """
        Met à jour le nom et/ou la description d'un appareil.

        Args:
            appliance_id: ID de l'appareil
            name: Nouveau nom (optionnel)
            description: Nouvelle description (optionnel)

        Returns:
            Appareil mis à jour ou None si non trouvé
        """
        # Construire dynamiquement la requête UPDATE
        set_clauses = []
        params = {"appliance_id": appliance_id}
        
        if name is not None:
            set_clauses.append("name = :name")
            params["name"] = name
        
        if description is not None:
            set_clauses.append("description = :description")
            params["description"] = description
        
        if not set_clauses:
            # Rien à mettre à jour, récupérer l'appareil actuel
            select_query = text("""
                SELECT id, name, description, created_at, updated_at
                FROM cnn_appliances
                WHERE id = :appliance_id
            """)
            with self.engine.connect() as conn:
                result = conn.execute(select_query, params).fetchone()
                if result:
                    return {
                        "id": result[0],
                        "name": result[1],
                        "description": result[2],
                        "created_at": format_datetime_utc(result[3]),
                        "updated_at": format_datetime_utc(result[4]),
                    }
                return None
        
        set_clauses.append("updated_at = NOW()")
        update_query = text(f"""
            UPDATE cnn_appliances
            SET {", ".join(set_clauses)}
            WHERE id = :appliance_id
            RETURNING id, name, description, created_at, updated_at
        """)

        with self.engine.connect() as conn:
            result = conn.execute(update_query, params).fetchone()
            
            if result:
                conn.commit()
                return {
                    "id": result[0],
                    "name": result[1],
                    "description": result[2],
                    "created_at": format_datetime_utc(result[3]),
                    "updated_at": format_datetime_utc(result[4]),
                }
            return None

    def delete_appliance(self, appliance_id: int) -> dict[str, int] | None:
        """
        Supprime un appareil et toutes ses données associées.

        Args:
            appliance_id: ID de l'appareil à supprimer

        Returns:
            Dictionnaire avec le nombre de signatures et détections supprimées
        """
        # Vérifier d'abord que l'appareil existe
        check_query = text("""
            SELECT id FROM cnn_appliances WHERE id = :appliance_id
        """)

        with self.engine.connect() as conn:
            exists = conn.execute(
                check_query,
                {"appliance_id": appliance_id}
            ).fetchone()
            
            if not exists:
                return None

            # Compter les éléments à supprimer
            count_signatures_query = text("""
                SELECT COUNT(*) FROM cnn_signatures WHERE appliance_id = :appliance_id
            """)
            count_detections_query = text("""
                SELECT COUNT(*) FROM cnn_detections WHERE appliance_id = :appliance_id
            """)

            signatures_count = conn.execute(
                count_signatures_query,
                {"appliance_id": appliance_id}
            ).scalar()
            
            detections_count = conn.execute(
                count_detections_query,
                {"appliance_id": appliance_id}
            ).scalar()

            # Supprimer dans l'ordre (FK constraints)
            delete_detections_query = text("""
                DELETE FROM cnn_detections WHERE appliance_id = :appliance_id
            """)
            delete_signatures_query = text("""
                DELETE FROM cnn_signatures WHERE appliance_id = :appliance_id
            """)
            delete_appliance_query = text("""
                DELETE FROM cnn_appliances WHERE id = :appliance_id
            """)

            conn.execute(delete_detections_query, {"appliance_id": appliance_id})
            conn.execute(delete_signatures_query, {"appliance_id": appliance_id})
            conn.execute(delete_appliance_query, {"appliance_id": appliance_id})
            
            conn.commit()

            return {
                "signatures_deleted": signatures_count or 0,
                "detections_deleted": detections_count or 0,
            }

    def _get_average_consumption(self) -> float | None:
        """Récupère la puissance moyenne des dernières 48h."""
        query = text("""
            SELECT AVG(papp)
            FROM linky_realtime
            WHERE time >= NOW() - INTERVAL '48 hours'
        """)

        with self.engine.connect() as conn:
            result = conn.execute(query).fetchone()
            if result and result[0] is not None:
                return float(result[0])
            return None

    def get_cnn_models_paginated(
        self, page: int = 1, per_page: int = 10
    ) -> dict[str, Any]:
        """
        Récupère les modèles CNN avec pagination.

        Args:
            page: Numéro de page (commence à 1)
            per_page: Nombre de modèles par page

        Returns:
            Dictionnaire avec total, total_pages et liste de modèles
        """
        # Calculer l'offset
        offset = (page - 1) * per_page

        # Requête pour le total
        count_query = text("""
            SELECT COUNT(*) FROM cnn_models
        """)

        # Requête pour les modèles paginés
        query = text("""
            SELECT
                id,
                version,
                model_type,
                architecture,
                training_date,
                num_signatures,
                num_classes,
                metrics,
                model_path,
                is_active,
                training_duration_seconds
            FROM cnn_models
            ORDER BY training_date DESC
            LIMIT :limit OFFSET :offset
        """)

        with self.engine.connect() as conn:
            # Récupérer le total
            total = conn.execute(count_query).scalar() or 0
            
            # Calculer le nombre total de pages
            total_pages = (
                (total + per_page - 1) // per_page if total > 0 else 0
            )

            # Récupérer les modèles
            result = conn.execute(
                query,
                {"limit": per_page, "offset": offset}
            ).fetchall()

            models = []
            for row in result:
                models.append({
                    "id": row[0],
                    "version": row[1],
                    "model_type": row[2],
                    "architecture": row[3],
                    "training_date": format_datetime_utc(row[4]),
                    "num_signatures": row[5],
                    "num_classes": row[6],
                    "metrics": row[7],
                    "model_path": row[8],
                    "is_active": row[9],
                    "training_duration_seconds": row[10],
                })

            return {
                "total": total,
                "total_pages": total_pages,
                "models": models,
            }

    def delete_cnn_model(self, model_id: int) -> dict[str, Any]:
        """
        Supprime un modèle CNN de la base de données et du filesystem.

        Args:
            model_id: ID du modèle à supprimer

        Returns:
            Dictionnaire avec le statut de suppression

        Raises:
            ValueError: Si le modèle est actif ou n'existe pas
        """
        # Vérifier que le modèle existe et n'est pas actif
        check_query = text("""
            SELECT id, version, is_active, model_path
            FROM cnn_models
            WHERE id = :model_id
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                check_query, {"model_id": model_id}
            ).fetchone()
            
            if not result:
                raise ValueError(f"Modèle {model_id} non trouvé")
            
            model_id_db, version, is_active, model_path = result
            
            if is_active:
                raise ValueError(
                    f"Impossible de supprimer le modèle actif "
                    f"(version {version})"
                )
            
            # Supprimer de la base de données
            delete_query = text("""
                DELETE FROM cnn_models
                WHERE id = :model_id
            """)
            
            conn.execute(delete_query, {"model_id": model_id})
            conn.commit()
            
            return {
                "id": model_id_db,
                "version": version,
                "model_path": model_path,
                "deleted": True,
            }

    def delete_detection(self, detection_id: int) -> dict[str, Any] | None:
        """
        Supprime une détection spécifique de la base de données.

        Args:
            detection_id: ID de la détection à supprimer

        Returns:
            Dictionnaire avec les informations de la détection supprimée
            ou None si la détection n'existe pas
        """
        # Vérifier que la détection existe et récupérer ses informations
        check_query = text("""
            SELECT
                cd.id,
                cd.appliance_id,
                ca.name,
                cd.start_time,
                cd.end_time
            FROM cnn_detections cd
            JOIN cnn_appliances ca ON cd.appliance_id = ca.id
            WHERE cd.id = :detection_id
        """)

        with self.engine.connect() as conn:
            result = conn.execute(
                check_query,
                {"detection_id": detection_id}
            ).fetchone()
            
            if not result:
                return None
            
            detection_info = {
                "id": result[0],
                "appliance_id": result[1],
                "appliance_name": result[2],
                "start_time": format_datetime_utc(result[3]),
                "end_time": format_datetime_utc(result[4]),
            }
            
            # Supprimer la détection
            delete_query = text("""
                DELETE FROM cnn_detections
                WHERE id = :detection_id
            """)
            
            conn.execute(delete_query, {"detection_id": detection_id})
            conn.commit()
            
            return detection_info


# Instance globale du gestionnaire de base de données
db_manager = DatabaseManager()
