.PHONY: help build up down logs restart clean init-sync stats start check redis-cli status scale-workers

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

start: ## Démarre l'application complète (build + up + info)
	@echo "=========================================="
	@echo "🚀 Démarrage de Nilmia"
	@echo "=========================================="
	@echo ""
	@if [ ! -f ".env" ]; then \
		echo "❌ Le fichier .env n'existe pas à la racine"; \
		echo "📝 Copie du fichier .env.example..."; \
		cp .env.example .env; \
		echo "✅ Fichier .env créé, veuillez le configurer avant de continuer"; \
		exit 1; \
	fi
	@echo "✅ Fichier .env trouvé"
	@echo ""
	@echo "🔨 Construction des images Docker..."
	@docker-compose build
	@echo ""
	@echo "🚀 Démarrage des services..."
	@docker-compose up -d
	@echo ""
	@echo "⏳ Attente du démarrage des services..."
	@sleep 10
	@echo ""
	@echo "📊 État des services:"
	@docker-compose ps
	@echo ""
	@echo "=========================================="
	@echo "✅ Services démarrés avec succès !"
	@echo "=========================================="
	@echo ""
	@echo "📊 Flower (monitoring Celery): http://localhost:5555"
	@echo "🗄️  pgAdmin (TimescaleDB): http://localhost:8080"
	@echo "🗄️  TimescaleDB: localhost:5432"
	@echo "🔴 Redis: localhost:6379"
	@echo "🌐 Backend API: http://localhost:8000"
	@echo "🎨 Frontend React: http://localhost:3000"
	@echo ""
	@echo "🧠 Service NILM activé avec GPU"
	@echo "   - Training automatique toutes les 24h"
	@echo "   - Détection toutes les 5 minutes"
	@echo "   - Utilisez 'make nilm-stats' pour voir les détections"
	@echo ""
	@echo "=========================================="

check: ## Vérifie l'état des services et affiche les statistiques
	@echo "=========================================="
	@echo "🔍 Vérification des services"
	@echo "=========================================="
	@echo ""
	@echo "📦 Services Docker:"
	@echo ""
	@if docker ps | grep nilmia-timescaledb | grep -q healthy; then \
		echo "✅ TimescaleDB"; \
	else \
		echo "❌ TimescaleDB"; \
	fi
	@if docker ps | grep nilmia-redis | grep -q healthy; then \
		echo "✅ Redis"; \
	else \
		echo "❌ Redis"; \
	fi
	@if docker ps | grep nilmia-sync-worker | grep -q Up; then \
		echo "✅ Sync Worker"; \
	else \
		echo "❌ Sync Worker"; \
	fi
	@if docker ps | grep nilmia-sync-beat | grep -q Up; then \
		echo "✅ Sync Beat"; \
	else \
		echo "❌ Sync Beat"; \
	fi
	@if docker ps | grep nilmia-nilm-worker | grep -q Up; then \
		echo "✅ NILM Worker"; \
	else \
		echo "❌ NILM Worker"; \
	fi
	@if docker ps | grep nilmia-nilm-beat | grep -q Up; then \
		echo "✅ NILM Beat"; \
	else \
		echo "❌ NILM Beat"; \
	fi
	@if docker ps | grep nilmia-flower | grep -q Up; then \
		echo "✅ Flower"; \
	else \
		echo "❌ Flower"; \
	fi
	@if docker ps | grep nilmia-pgadmin | grep -q Up; then \
		echo "✅ pgAdmin"; \
	else \
		echo "❌ pgAdmin"; \
	fi
	@if docker ps | grep nilmia-backend | grep -q healthy; then \
		echo "✅ Backend API"; \
	else \
		echo "❌ Backend API"; \
	fi
	@if docker ps | grep nilmia-frontend | grep -q Up; then \
		echo "✅ Frontend React"; \
	else \
		echo "❌ Frontend React"; \
	fi
	@echo ""
	@echo "=========================================="
	@echo "📊 Statistiques de la base de données"
	@echo "=========================================="
	@echo ""
	@docker exec nilmia-timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			COUNT(*) as \"📝 Total mesures\", \
			TO_CHAR(MIN(time), 'DD/MM/YYYY HH24:MI:SS') as \"📅 Première mesure\", \
			TO_CHAR(MAX(time), 'DD/MM/YYYY HH24:MI:SS') as \"📅 Dernière mesure\", \
			ROUND(AVG(papp)::numeric, 2) || ' VA' as \"⚡ Puissance moyenne\", \
			MAX(papp) || ' VA' as \"📈 Puissance max\", \
			ROUND(AVG(temperature)::numeric, 2) || ' °C' as \"🌡️ Température moyenne\" \
		FROM linky_realtime;" 2>/dev/null || echo "❌ Impossible de récupérer les statistiques"
	@echo ""
	@echo "=========================================="
	@echo "🔄 Dernières synchronisations"
	@echo "=========================================="
	@echo ""
	@docker logs nilmia-sync-worker 2>&1 | grep -E "nouveaux enregistrements insérés|Task incremental_sync.*succeeded" | tail -3 || echo "Aucune synchronisation récente trouvée"
	@echo ""
	@echo "=========================================="
	@echo "🌐 URLs d'accès"
	@echo "=========================================="
	@echo ""
	@echo "Flower (monitoring)  : http://localhost:5555"
	@echo "pgAdmin (TimescaleDB): http://localhost:8080"
	@echo "Backend API          : http://localhost:8000"
	@echo "Frontend React       : http://localhost:3000"
	@echo "TimescaleDB          : localhost:5432"
	@echo "Redis                : localhost:6379"
	@echo ""
	@echo "=========================================="
	@echo "📝 Commandes rapides"
	@echo "=========================================="
	@echo ""
	@echo "make stats          # Voir les statistiques"
	@echo "make logs           # Voir tous les logs"
	@echo "make flower         # Ouvrir Flower"
	@echo "make psql           # Se connecter à la base"
	@echo ""

build: ## Construit les images Docker
	@DOCKER_BUILDKIT=1 docker-compose build

up: ## Démarre tous les services
	docker-compose up -d

down: ## Arrête tous les services
	docker-compose down

logs: ## Affiche les logs de tous les services
	docker-compose logs -f

restart: ## Redémarre tous les services
	docker-compose restart

clean: ## Supprime tous les containers et volumes
	docker-compose down -v

flower: ## Ouvre Flower dans le navigateur
	@echo "Flower: http://localhost:5555"
	@echo "Ouvrez http://localhost:5555 dans votre navigateur"

psql: ## Se connecte à TimescaleDB via psql
	docker exec -it nilmia-timescaledb psql -U postgres -d local_data

pgadmin: ## Ouvre pgAdmin dans le navigateur
	@echo "pgAdmin: http://localhost:8080"
	@echo "Email: admin@example.com | Password: admin"
	@echo "Ouvrez http://localhost:8080 dans votre navigateur"

backend: ## Affiche l'URL du backend et teste l'API
	@echo "Backend API: http://localhost:8000"
	@echo ""
	@echo "📊 Test de l'API:"
	@curl -s http://localhost:8000/health | jq . || echo "❌ Backend non accessible"

frontend: ## Ouvre le frontend dans le navigateur
	@echo "Frontend React: http://localhost:3000"
	@echo "Ouvrez http://localhost:3000 dans votre navigateur"

api-latest: ## Récupère la dernière consommation via l'API
	@echo "📊 Dernière consommation:"
	@curl -s http://localhost:8000/api/consumption/latest | jq .

api-history: ## Récupère l'historique via l'API (usage: make api-history HOURS=24)
	@echo "📈 Historique de consommation (${HOURS} heures):"
	@curl -s "http://localhost:8000/api/consumption/history?hours=${HOURS}" | jq '.data | length' || echo "Erreur"

# Valeur par défaut pour HOURS
HOURS ?= 24

api-detections: ## Récupère les détections via l'API
	@echo "🔌 Détections d'appareils:"
	@curl -s http://localhost:8000/api/detections | jq '.detections | length' || echo "Erreur"

nilm-train: ## Lance l'entraînement du modèle NILM
	@echo "🧠 Lancement de l'entraînement du modèle NILM..."
	docker exec nilmia-nilm-worker celery -A src.tasks.celery_app call train_nilm_model --queue=nilm

nilm-detect: ## Lance une détection manuelle d'appareils
	@echo "🔍 Lancement de la détection d'appareils..."
	docker exec nilmia-nilm-worker celery -A src.tasks.celery_app call detect_appliances_task --queue=nilm

nilm-stats: ## Affiche les statistiques de détection NILM
	@echo "=========================================="
	@echo "📊 Statistiques NILM"
	@echo "=========================================="
	@echo ""
	@echo "🔌 Appareils détectés:"
	@docker exec nilmia-timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			a.name as \"Appareil\", \
			a.is_validated as \"Validé\", \
			COUNT(d.id) as \"Détections\", \
			ROUND(SUM(d.energy_consumed)::numeric, 2) || ' Wh' as \"Énergie consommée\", \
			ROUND(AVG(d.avg_power)::numeric, 2) || ' VA' as \"Puissance moyenne\", \
			ROUND(AVG(d.confidence_score)::numeric, 2) as \"Confiance moy.\" \
		FROM appliances a \
		LEFT JOIN detection_events d ON a.id = d.appliance_id \
		GROUP BY a.id, a.name, a.is_validated \
		ORDER BY SUM(d.energy_consumed) DESC NULLS LAST;" 2>/dev/null || echo "❌ Erreur de récupération des stats"
	@echo ""
	@echo "📈 Dernières détections:"
	@docker exec nilmia-timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			a.name as \"Appareil\", \
			TO_CHAR(d.start_time, 'DD/MM HH24:MI') as \"Début\", \
			TO_CHAR(d.end_time, 'DD/MM HH24:MI') as \"Fin\", \
			ROUND(d.avg_power::numeric, 0) || ' VA' as \"Puissance\", \
			ROUND(d.energy_consumed::numeric, 2) || ' Wh' as \"Énergie\", \
			ROUND(d.confidence_score::numeric, 2) as \"Confiance\" \
		FROM detection_events d \
		JOIN appliances a ON d.appliance_id = a.id \
		ORDER BY d.start_time DESC \
		LIMIT 10;" 2>/dev/null || echo "❌ Erreur de récupération des détections"
	@echo ""

nilm-models: ## Liste les modèles ML entraînés
	@echo "🤖 Modèles ML:"
	@docker exec nilmia-timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			version as \"Version\", \
			model_type as \"Type\", \
			TO_CHAR(training_date, 'DD/MM/YYYY HH24:MI') as \"Date entraînement\", \
			is_active as \"Actif\", \
			(metrics->>'silhouette_score')::numeric as \"Silhouette Score\" \
		FROM model_versions \
		ORDER BY training_date DESC \
		LIMIT 5;" 2>/dev/null || echo "❌ Aucun modèle trouvé"

redis-cli: ## Se connecte à Redis via redis-cli
	docker exec -it nilmia-redis redis-cli

status: ## Affiche le statut des services
	docker-compose ps

scale-workers: ## Scale les workers (usage: make scale-workers N=3)
	docker-compose up -d --scale sync-worker=$(N)
