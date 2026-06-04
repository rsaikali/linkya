.PHONY: help build up down logs restart clean status deploy train detect lint

# docker-compose.yml = PROD. docker-compose.override.yml (dev) is auto-loaded
# by `docker compose` locally. On the Pi, deploy uses -f to skip the override.
COMPOSE      = docker compose
COMPOSE_PROD = docker compose -f docker-compose.yml

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-18s\033[0m %s\n", $$1, $$2}'

# ── Dev (override auto-loaded) ───────────────
build: ## Build images (dev)
	@DOCKER_BUILDKIT=1 $(COMPOSE) build

up: ## Start all services (dev)
	@$(COMPOSE) up -d

down: ## Stop all services
	@$(COMPOSE) down

clean: ## Stop + delete volumes (wipes all data)
	@$(COMPOSE) down -v

status: ## Container status
	@$(COMPOSE) ps

logs: ## Tail all logs
	@$(COMPOSE) logs -f

restart: ## Restart all services
	@$(COMPOSE) restart

# ── Prod (Pi, CD) ────────────────────────────
deploy: ## Prod build + restart on the Pi (CD target, no dev override)
	@DOCKER_BUILDKIT=1 $(COMPOSE_PROD) build
	@$(COMPOSE_PROD) up -d
	@$(COMPOSE_PROD) ps

# ── NILM ─────────────────────────────────────
train: ## Trigger training via API
	@curl -s -X POST http://localhost:8000/api/nilm/train | python3 -m json.tool

detect: ## Trigger detection (full history) via API
	@curl -s -X POST http://localhost:8000/api/nilm/detect | python3 -m json.tool

# ── Quality ──────────────────────────────────
lint: ## flake8 + isort check
	@flake8 backend-service/src nilm-service/src ha-ingest-service/src ha-publish-service/src || true
	@isort --check-only --diff backend-service/src nilm-service/src ha-ingest-service/src ha-publish-service/src || true
