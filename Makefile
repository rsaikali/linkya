.PHONY: help build up down logs restart clean init-sync stats start check redis-cli status scale-workers

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

build: ## Construit les images Docker
	@DOCKER_BUILDKIT=1 docker-compose build

up: ## Démarre tous les services
	docker-compose up -d

down: ## Arrête tous les services
	docker-compose down

status: ## Affiche le statut des services
	docker-compose ps

logs: ## Affiche les logs de tous les services
	docker-compose logs -f

restart: ## Redémarre tous les services
	docker-compose restart

clean: ## Supprime tous les containers et volumes
	docker-compose down -v

train: ## Lance l'entraînement NILM via l'API (utilise automatiquement les feedbacks utilisateur)
	@echo "🧠 Lancement de l'entraînement via l'API (avec apprentissage par feedback)..."
	@curl -X POST http://localhost:8000/api/nilm/train | python3 -m json.tool

detect: ## Lance la détection NILM via l'API
	@echo "🔍 Lancement de la détection via l'API..."
	@curl -X POST http://localhost:8000/api/nilm/detect | python3 -m json.tool

feedback-stats: ## Affiche les statistiques des feedbacks utilisateur
	@echo "📊 Statistiques des feedbacks utilisateur..."
	@docker-compose exec timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			ca.name AS appareil, \
			COUNT(CASE WHEN cd.is_correct = TRUE THEN 1 END) AS validations, \
			COUNT(CASE WHEN cd.is_correct = FALSE THEN 1 END) AS invalidations, \
			COUNT(CASE WHEN cd.user_validated IS NULL THEN 1 END) AS non_validees \
		FROM cnn_detections cd \
		JOIN cnn_appliances ca ON cd.appliance_id = ca.id \
		GROUP BY ca.name \
		ORDER BY (COUNT(CASE WHEN cd.is_correct = FALSE THEN 1 END)) DESC;"

signatures-stats: ## Affiche les statistiques des signatures (positives et négatives)
	@echo "📊 Statistiques des signatures..."
	@docker-compose exec timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			ca.name AS appareil, \
			COUNT(CASE WHEN cs.is_negative = FALSE THEN 1 END) AS positives, \
			COUNT(CASE WHEN cs.is_negative = TRUE THEN 1 END) AS negatives \
		FROM cnn_signatures cs \
		JOIN cnn_appliances ca ON cs.appliance_id = ca.id \
		GROUP BY ca.name \
		ORDER BY ca.name;"

detections-clean: ## Vide la table des détections (les signatures négatives sont préservées)
	@echo "⚠️  Nettoyage de la table des détections..."
	@docker-compose exec timescaledb psql -U postgres -d local_data -c "\
		DELETE FROM cnn_detections; \
		SELECT 'Toutes les détections ont été supprimées. Les signatures négatives sont préservées.' AS status;"
	@echo "✅ Nettoyage terminé. Vous pouvez relancer make detect pour générer de nouvelles détections."

init-sync: ## Initialise la synchronisation des données


model-compare: ## Compare les métriques du modèle current vs backup
	@echo "📊 Comparaison Current vs Backup..."
	@docker-compose exec timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			model_status, \
			version, \
			training_date, \
			num_signatures, \
			num_classes as appareils, \
			training_duration_seconds as duree_s, \
			metrics->'appliances' as details_appareils \
		FROM cnn_models \
		WHERE model_status IN ('current', 'backup') \
		ORDER BY CASE model_status WHEN 'current' THEN 1 WHEN 'backup' THEN 2 END;"

model-rollback: ## Revient au modèle backup (annule le dernier entraînement)
	@echo "⚠️  Rollback vers le modèle backup..."
	@docker-compose exec timescaledb psql -U postgres -d local_data -c "\
		BEGIN; \
		UPDATE cnn_models SET model_status = 'archived' WHERE model_status = 'current'; \
		UPDATE cnn_models SET model_status = 'current' WHERE model_status = 'backup'; \
		COMMIT; \
		SELECT 'Rollback effectué ! Modèle backup promu en current.' AS status;"
	@echo "✅ Rollback terminé. Relancez make detect pour utiliser le modèle restauré."

model-status: ## Affiche le statut actuel des modèles (current/backup/archived)
	@echo "📋 Statut des modèles..."
	@docker-compose exec timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			model_status, \
			version, \
			model_type, \
			training_date, \
			num_signatures, \
			num_classes as appareils \
		FROM cnn_models \
		ORDER BY CASE model_status WHEN 'current' THEN 1 WHEN 'backup' THEN 2 ELSE 3 END, training_date DESC;"

frontend-logs: ## Affiche les logs du frontend
	@docker-compose logs -f frontend

frontend-restart: ## Redémarre le frontend
	@docker-compose restart frontend

frontend-reload: ## Force le rechargement du frontend (utile sur WSL2)
	@echo "🔄 Rechargement du frontend..."
	@docker exec nilmia-frontend touch /app/src/index.js
	@echo "✅ Rechargement déclenché. Vérifiez votre navigateur."
