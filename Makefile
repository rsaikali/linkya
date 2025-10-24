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

train: ## Lance l'entraînement NILM via l'API
	@echo "🧠 Lancement de l'entraînement via l'API..."
	@curl -X POST http://localhost:8000/api/nilm/train | python3 -m json.tool

detect: ## Lance la détection NILM via l'API
	@echo "🔍 Lancement de la détection via l'API..."
	@curl -X POST http://localhost:8000/api/nilm/detect | python3 -m json.tool