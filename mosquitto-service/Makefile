.PHONY: help build up down restart logs status clean test backup restore

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

###############################################
## Service Management
###############################################
build: ## Construit l'image Docker Mosquitto
	@echo "Building Mosquitto image for ARM 32-bit..."
	docker compose build

up: ## Démarre le service Mosquitto
	docker compose up -d

down: ## Arrête le service Mosquitto
	docker compose down

restart: ## Redémarre le service Mosquitto
	docker compose restart

logs: ## Affiche les logs en temps réel
	docker compose logs -f

status: ## Affiche le statut du service
	docker compose ps

clean: ## Supprime le container et les volumes (DESTRUCTIF)
	@echo "WARNING: This will delete all data and certificates!"
	@read -p "Are you sure? (yes/no): " confirm && [ "$$confirm" = "yes" ]
	docker compose down -v

###############################################
## Testing & Monitoring
###############################################
test: ## Test la connexion MQTT
	@echo "Testing MQTT connection..."
	@docker compose exec mosquitto mosquitto_pub -h localhost -p 1883 \
		-t "test/connection" -m "Test from Makefile" \
		-u admin -P "$$(grep MQTT_ADMIN_PASSWORD .env | cut -d= -f2)"

stats: ## Affiche les statistiques du broker
	@echo "Subscribing to broker statistics..."
	@docker compose exec mosquitto mosquitto_sub -h localhost -p 1883 \
		-t '$$SYS/broker/#' -C 10 \
		-u admin -P "$$(grep MQTT_ADMIN_PASSWORD .env | cut -d= -f2)"

shell: ## Accès shell au container
	docker compose exec mosquitto sh

###############################################
## Certificate Management
###############################################
certs-generate: ## Régénère les certificats TLS
	@echo "Regenerating TLS certificates..."
	docker compose exec mosquitto /mosquitto/scripts/generate-certs.sh

certs-export: ## Exporte le certificat CA
	@echo "Exporting CA certificate..."
	docker compose cp mosquitto:/mosquitto/certs/ca.crt ./ca.crt
	@echo "CA certificate exported to: ./ca.crt"

certs-info: ## Affiche les informations des certificats
	@echo "CA Certificate:"
	@docker compose exec mosquitto openssl x509 -in /mosquitto/certs/ca.crt -text -noout | grep -E "(Subject|Issuer|Not Before|Not After)"
	@echo ""
	@echo "Server Certificate:"
	@docker compose exec mosquitto openssl x509 -in /mosquitto/certs/server.crt -text -noout | grep -E "(Subject|Issuer|Not Before|Not After|DNS|IP)"

###############################################
## User Management
###############################################
users-list: ## Liste les utilisateurs configurés
	@echo "Configured users:"
	@docker compose exec mosquitto grep -o '^[^:]*' /mosquitto/config/passwd

users-regenerate: ## Régénère le fichier de mots de passe
	@echo "Regenerating password file..."
	docker compose exec mosquitto /mosquitto/scripts/generate-passwords.sh

###############################################
## Backup & Restore
###############################################
backup: ## Sauvegarde les données et certificats
	@echo "Creating backup..."
	@mkdir -p ./backups
	@docker compose exec mosquitto tar czf /tmp/mosquitto-backup.tar.gz \
		/mosquitto/data /mosquitto/certs /mosquitto/config/passwd
	@docker compose cp mosquitto:/tmp/mosquitto-backup.tar.gz \
		./backups/mosquitto-backup-$$(date +%Y%m%d-%H%M%S).tar.gz
	@echo "Backup saved to: ./backups/"

restore: ## Restaure depuis une sauvegarde (usage: make restore BACKUP=backups/mosquitto-backup-20251113-143000.tar.gz)
	@if [ -z "$(BACKUP)" ]; then \
		echo "Error: BACKUP parameter required"; \
		echo "Usage: make restore BACKUP=backups/mosquitto-backup-YYYYMMDD-HHMMSS.tar.gz"; \
		exit 1; \
	fi
	@echo "Restoring from: $(BACKUP)"
	@docker compose cp $(BACKUP) mosquitto:/tmp/restore.tar.gz
	@docker compose exec mosquitto tar xzf /tmp/restore.tar.gz -C /
	@docker compose restart
	@echo "Restore completed"

###############################################
## System Information
###############################################
info: ## Affiche les informations système
	@echo "=== System Information ==="
	@echo "Architecture: $$(uname -m)"
	@echo "Docker version: $$(docker --version)"
	@echo "Docker Compose version: $$(docker compose version)"
	@echo ""
	@echo "=== Mosquitto Service ==="
	@docker compose ps
	@echo ""
	@echo "=== Resource Usage ==="
	@docker stats --no-stream mosquitto

version: ## Affiche la version de Mosquitto
	@docker compose exec mosquitto mosquitto -h | head -n 1
