.PHONY: help build up down logs restart clean init-sync stats start check redis-cli status scale-workers

help: ## Affiche l'aide
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-20s\033[0m %s\n", $$1, $$2}'

###############################################
## Docker Compose Management
###############################################
build: ## Construit les images Docker
	@DOCKER_BUILDKIT=1 docker-compose build

deploy: ## Deploy on Pi (CD): prod build + restart (uses docker-compose.prod.yml)
	@DOCKER_BUILDKIT=1 docker-compose -f docker-compose.yml -f docker-compose.prod.yml build
	@docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d
	@docker-compose -f docker-compose.yml -f docker-compose.prod.yml ps

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
	@nilm-service/.venv/bin/flake8 nilm-service/src/ || true
	@echo "--------------------------------"
	@echo "Checking import order with isort..."
	@backend-service/.venv/bin/isort --check-only --diff backend-service/src/ || true
	@nilm-service/.venv/bin/isort --check-only --diff nilm-service/src/ || true
	@echo "✓ Code quality check completed!"

code-quality-fix: ## Fix Python code quality issues (Black + isort + trailing whitespace)
	@echo "Sorting imports with isort..."
	@backend-service/.venv/bin/isort backend-service/src/
	@nilm-service/.venv/bin/isort nilm-service/src/
	@echo "--------------------------------"
	@echo "Formatting code with Black..."
	@backend-service/.venv/bin/black backend-service/src/
	@nilm-service/.venv/bin/black nilm-service/src/
	@echo "--------------------------------"
	@echo "Removing trailing whitespace..."
	@find backend-service/src nilm-service/src -name "*.py" -type f -exec sed -i 's/[[:space:]]*$$//' {} +
	@echo "✓ Code quality fix completed!"
