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
	@if docker ps | grep nilmia-cnn-worker | grep -q Up; then \
		echo "✅ CNN Worker"; \
	else \
		echo "❌ CNN Worker"; \
	fi
	@if docker ps | grep nilmia-cnn-beat | grep -q Up; then \
		echo "✅ CNN Beat"; \
	else \
		echo "❌ CNN Beat"; \
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

# Commandes NILM-CNN
cnn-appliances: ## Liste les appareils CNN avec leurs signatures
	@echo "🔌 Appareils CNN:"
	@docker exec nilmia-timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			ca.name as \"Appareil\", \
			ca.description as \"Description\", \
			ca.num_signatures as \"Signatures\", \
			ROUND(ca.avg_power::numeric, 0) || ' VA' as \"Puissance moy.\", \
			ca.is_validated as \"Validé\" \
		FROM cnn_appliances ca \
		ORDER BY ca.num_signatures DESC;" 2>/dev/null || echo "❌ Aucun appareil trouvé"

cnn-train: ## Lance l'entraînement du modèle CNN
	@echo "🧠 Lancement de l'entraînement du modèle CNN..."
	docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call train_cnn_model --queue=nilm_cnn

cnn-detect: ## Lance une détection manuelle CNN (sur la période configurée)
	@echo "🔍 Lancement de la détection d'appareils (CNN)..."
	docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call detect_cnn_appliances --queue=nilm_cnn

cnn-stats: ## Affiche les statistiques CNN NILM
	@echo "=========================================="
	@echo "📊 Statistiques NILM-CNN"
	@echo "=========================================="
	@echo ""
	@docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call get_cnn_stats --queue=nilm_cnn | tail -n +3 | jq '.'
	@echo ""

cnn-add-signature: ## Ajoute une signature CNN (exemple)
	@echo "📝 Ajout d'une signature CNN (exemple)..."
	@echo "⚠️  Modifiez les paramètres selon vos besoins"
	docker exec nilmia-cnn-worker celery -A src.tasks.celery_app call add_cnn_signature \
		--kwargs='{"appliance_name": "Lave-linge", "start_time_str": "2025-10-22T10:00:00Z", "end_time_str": "2025-10-22T11:30:00Z", "mode": "eco"}' \
		--queue=nilm_cnn

cnn-models: ## Liste les modèles CNN entraînés
	@echo "🤖 Modèles CNN:"
	@docker exec nilmia-timescaledb psql -U postgres -d local_data -c "\
		SELECT \
			version as \"Version\", \
			model_type as \"Type\", \
			TO_CHAR(training_date, 'DD/MM/YYYY HH24:MI') as \"Date entraînement\", \
			num_classes as \"Classes\", \
			is_active as \"Actif\", \
			(metrics->>'val_accuracy')::numeric as \"Accuracy\" \
		FROM cnn_models \
		ORDER BY training_date DESC \
		LIMIT 5;" 2>/dev/null || echo "❌ Aucun modèle CNN trouvé"

redis-cli: ## Se connecte à Redis via redis-cli
	docker exec -it nilmia-redis redis-cli

status: ## Affiche le statut des services
	docker-compose ps

scale-workers: ## Scale les workers (usage: make scale-workers N=3)
	docker-compose up -d --scale sync-worker=$(N)

