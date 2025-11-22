.PHONY: help build up down logs restart clean init-sync stats start check redis-cli status scale-workers

# Load environment variables from .env file
include .env
export

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

###############################################
## Docker Compose Management
###############################################
build: ## Construit les images Docker
	@DOCKER_BUILDKIT=1 docker compose build

up: ## Démarre tous les services
	docker compose up -d

down: ## Arrête tous les services
	docker compose down

status: ## Affiche le statut des services
	docker compose ps

logs: ## Affiche les logs de tous les services
	docker compose logs -f

restart: ## Redémarre tous les services
	docker compose restart

clean: ## Supprime tous les containers et volumes
	docker compose down -v

###############################################
## MQTT Service Management
###############################################
mqtt-test: ## Test la connexion MQTT avec le broker
	@echo "Test de connexion MQTT..."
	@bash -c 'source .env && docker compose exec mosquitto mosquitto_pub -h localhost -p 1883 -t "test/connection" -m "Hello from Linkya" -u admin -P "$$MQTT_ADMIN_PASSWORD"'

mqtt-logs: ## Affiche les logs du broker MQTT
	@docker compose logs -f mosquitto

mqtt-listen: ## Écoute tous les messages MQTT en temps réel
	@echo "Écoute de tous les topics MQTT (Ctrl+C pour arrêter)..."
	@bash -c 'source .env && docker compose exec mosquitto mosquitto_sub -h localhost -p 1883 -t "#" -v -u admin -P "$$MQTT_ADMIN_PASSWORD"'

mqtt-subscribe: ## S'abonne à un topic spécifique (usage: make mqtt-subscribe TOPIC=linkya/teleinfo)
	@echo "Écoute du topic: ${TOPIC}"
	@bash -c 'source .env && docker compose exec mosquitto mosquitto_sub -h localhost -p 1883 -t "${TOPIC}" -v -u admin -P "$$MQTT_ADMIN_PASSWORD"'

mqtt-stats: ## Affiche les statistiques détaillées du broker MQTT
	@echo "=== Statistiques du broker MQTT ==="
	@bash -c 'source .env && echo -n "Clients connectés: " && docker compose exec mosquitto mosquitto_sub -h localhost -p 1883 -t "$$SYS/broker/clients/connected" -C 1 -u admin -P "$$MQTT_ADMIN_PASSWORD" 2>/dev/null || echo "N/A"'
	@bash -c 'source .env && echo -n "Messages reçus: " && docker compose exec mosquitto mosquitto_sub -h localhost -p 1883 -t "$$SYS/broker/messages/received" -C 1 -u admin -P "$$MQTT_ADMIN_PASSWORD" 2>/dev/null || echo "N/A"'
	@bash -c 'source .env && echo -n "Messages envoyés: " && docker compose exec mosquitto mosquitto_sub -h localhost -p 1883 -t "$$SYS/broker/messages/sent" -C 1 -u admin -P "$$MQTT_ADMIN_PASSWORD" 2>/dev/null || echo "N/A"'
	@echo "==================================="

mqtt-status: ## Affiche le statut du broker MQTT
	@echo "Statistiques MQTT..."
	@bash -c 'source .env && docker compose exec mosquitto mosquitto_pub -h localhost -p 1883 -t "$$SYS/broker/clients/connected" -m "" -u admin -P "$$MQTT_ADMIN_PASSWORD"' || true

mqtt-certs-regen: ## Régénère les certificats TLS
	@echo "Régénération des certificats TLS..."
	@docker compose exec mosquitto /mosquitto/scripts/generate-certs.sh

mqtt-passwords-regen: ## Régénère le fichier de mots de passe
	@echo "Régénération des mots de passe..."
	@docker compose exec mosquitto /mosquitto/scripts/generate-passwords.sh

###############################################
## NILM Service Management via API
###############################################
train: ## Lance l'entraînement NILM via l'API (utilise automatiquement les feedbacks utilisateur)
	@echo "Lancement de l'entraînement via l'API (avec apprentissage par feedback)..."
	@curl -X POST http://localhost:8000/api/nilm/train | python3 -m json.tool

detect: ## Lance la détection NILM via l'API
	@echo "Lancement de la détection via l'API..."
	@curl -X POST http://localhost:8000/api/nilm/detect | python3 -m json.tool

###############################################
## Code Quality
###############################################
code-quality-check: ## Check Python code quality (Flake8 + isort)
	@echo "Checking with Flake8..."
	@backend-service/.venv/bin/flake8 backend-service/src/ || true
	@sync-service/.venv/bin/flake8 sync-service/src/ || true
	@nilm-service/.venv/bin/flake8 nilm-service/src/ || true
	@echo "--------------------------------"
	@echo "Checking import order with isort..."
	@backend-service/.venv/bin/isort --check-only --diff backend-service/src/ || true
	@sync-service/.venv/bin/isort --check-only --diff sync-service/src/ || true
	@nilm-service/.venv/bin/isort --check-only --diff nilm-service/src/ || true
	@echo "--------------------------------"
	@echo "✓ Code quality check completed!"

code-quality-fix: ## Fix Python code quality issues (Black + isort + trailing whitespace)
	@echo "Sorting imports with isort..."
	@backend-service/.venv/bin/isort backend-service/src/
	@sync-service/.venv/bin/isort sync-service/src/
	@nilm-service/.venv/bin/isort nilm-service/src/
	@echo "--------------------------------"
	@echo "Formatting code with Black..."
	@backend-service/.venv/bin/black backend-service/src/
	@sync-service/.venv/bin/black sync-service/src/
	@nilm-service/.venv/bin/black nilm-service/src/
	@echo "--------------------------------"
	@echo "Removing trailing whitespace..."
	@find backend-service/src sync-service/src nilm-service/src -name "*.py" -type f -exec sed -i 's/[[:space:]]*$$//' {} +
	@echo "--------------------------------"
	@echo "✓ Code quality fix completed!"
